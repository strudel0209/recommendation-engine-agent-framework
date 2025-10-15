"""Rules engine for module compatibility and constraint validation."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of compatibility validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    compatible_modules: List[str]
    incompatible_modules: List[str]


@dataclass
class RulesConfig:
    """Configuration for rules engine."""

    scale_equivalents: Dict[str, str]
    license_hierarchy: Dict[str, int]
    validation_settings: Dict[str, any]


class RulesEngine:
    """
    Validates module compatibility based on business rules.

    Rules:
    1. Dependency Resolution: All dependencies must be available
    2. Conflict Detection: Conflicting modules cannot coexist
    3. License Compatibility: License types must be compatible
    4. Scale Constraints: Modules must match building scale
    5. Theme Coherence: Check for theme-based conflicts
    """

    # Default configuration (used if config file not found)
    DEFAULT_CONFIG = {
        "scale_equivalents": {
            "small": "single-building",
            "low": "single-building",
            "single": "single-building",
            "single-building": "single-building",
            "medium": "multiple-buildings",
            "multiple": "multiple-buildings",
            "multiple-buildings": "multiple-buildings",
            "large": "campus",
            "campus": "campus",
            "enterprise": "portfolio",
            "portfolio": "portfolio",
            "multi-site": "portfolio",
        },
        "license_hierarchy": {"free": 0, "standard": 1, "premium": 2, "enterprise": 3},
        "validation_settings": {
            "max_theme_fragmentation": 2,
            "min_modules_for_theme_check": 3,
            "warn_on_free_tier_with_premium_license": True,
        },
    }

    def __init__(
        self,
        modules_catalog: List[Dict],
        config_path: Optional[str] = None,
        config_dict: Optional[Dict] = None,
    ):
        """
        Initialize rules engine with module catalog and configuration.

        Args:
            modules_catalog: List of all available modules
            config_path: Optional path to JSON configuration file
            config_dict: Optional configuration dictionary (overrides file)
        """
        self.modules_catalog = {m["id"]: m for m in modules_catalog}

        # Load configuration
        self.config = self._load_config(config_path, config_dict)

        logger.info(
            f"Initialized RulesEngine with {len(self.modules_catalog)} modules "
            f"and {len(self.config.scale_equivalents)} scale mappings"
        )

    def _load_config(
        self, config_path: Optional[str], config_dict: Optional[Dict]
    ) -> RulesConfig:
        """Load configuration from file or dictionary."""
        # Priority: config_dict > config_path > DEFAULT_CONFIG
        config_data = None

        if config_dict:
            config_data = config_dict
            logger.info("Using provided configuration dictionary")
        elif config_path:
            config_file = Path(config_path)
            if config_file.exists():
                try:
                    with open(config_file, "r") as f:
                        config_data = json.load(f)
                    logger.info(f"Loaded configuration from {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")
                    config_data = self.DEFAULT_CONFIG
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                config_data = self.DEFAULT_CONFIG
        else:
            config_data = self.DEFAULT_CONFIG
            logger.info("Using default configuration")

        return RulesConfig(
            scale_equivalents=config_data.get(
                "scale_equivalents", self.DEFAULT_CONFIG["scale_equivalents"]
            ),
            license_hierarchy=config_data.get(
                "license_hierarchy", self.DEFAULT_CONFIG["license_hierarchy"]
            ),
            validation_settings=config_data.get(
                "validation_settings", self.DEFAULT_CONFIG["validation_settings"]
            ),
        )

    @classmethod
    def from_config_file(cls, modules_catalog: List[Dict], config_path: str):
        """
        Create RulesEngine from configuration file.

        Args:
            modules_catalog: List of all available modules
            config_path: Path to JSON configuration file

        Returns:
            Configured RulesEngine instance
        """
        return cls(modules_catalog, config_path=config_path)

    def _normalize_scale_value(self, scale: str) -> str:
        """
        Normalize scale values using configured equivalents.
        No regex - simple dictionary lookup.
        """
        scale_lower = scale.lower().strip()
        return self.config.scale_equivalents.get(scale_lower, scale_lower)

    def validate_modules(
        self, module_ids: List[str], user_context: Optional[Dict] = None
    ) -> ValidationResult:
        """
        Validate compatibility of selected modules.

        Args:
            module_ids: List of module IDs to validate
            user_context: Optional context (scale, existing_modules, license_type)

        Returns:
            ValidationResult with errors, warnings, and compatible modules
        """
        errors = []
        warnings = []
        compatible = []
        incompatible = []

        if not module_ids:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                compatible_modules=[],
                incompatible_modules=[],
            )

        # Get user context
        user_scale = user_context.get("building_scale") if user_context else None
        existing_modules = (
            set(user_context.get("existing_modules", [])) if user_context else set()
        )
        user_license = user_context.get("license_type") if user_context else None

        # Track all modules (requested + existing)
        all_module_ids = set(module_ids) | existing_modules

        for module_id in module_ids:
            module = self.modules_catalog.get(module_id)
            if not module:
                errors.append(f"Module not found: {module_id}")
                incompatible.append(module_id)
                continue

            # Check 1: Dependency Resolution
            dep_errors = self._check_dependencies(module, all_module_ids)
            if dep_errors:
                errors.extend(dep_errors)
                incompatible.append(module_id)
                continue

            # Check 2: Conflict Detection
            conflict_errors = self._check_conflicts(module, all_module_ids)
            if conflict_errors:
                errors.extend(conflict_errors)
                incompatible.append(module_id)
                continue

            # Check 3: License Compatibility
            if user_license:
                license_issues = self._check_license(module, user_license)
                if license_issues["errors"]:
                    errors.extend(license_issues["errors"])
                    incompatible.append(module_id)
                    continue
                warnings.extend(license_issues["warnings"])

            # Check 4: Scale Constraints (data-driven)
            if user_scale:
                scale_issues = self._check_scale(module, user_scale)
                if scale_issues["errors"]:
                    errors.extend(scale_issues["errors"])
                    incompatible.append(module_id)
                    continue
                warnings.extend(scale_issues["warnings"])

            # Module passed all checks
            compatible.append(module_id)

        # Check 5: Theme Coherence (warning only)
        theme_warnings = self._check_theme_coherence(compatible)
        warnings.extend(theme_warnings)

        is_valid = len(errors) == 0

        logger.info(
            f"Validation: valid={is_valid}, "
            f"compatible={len(compatible)}, "
            f"incompatible={len(incompatible)}, "
            f"errors={len(errors)}, "
            f"warnings={len(warnings)}"
        )

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            compatible_modules=compatible,
            incompatible_modules=incompatible,
        )

    def _check_dependencies(self, module: Dict, all_modules: Set[str]) -> List[str]:
        """Check if all dependencies are satisfied."""
        errors = []
        dependencies = module.get("dependencies", [])

        for dep in dependencies:
            if dep not in all_modules:
                errors.append(
                    f"Module '{module['name']}' requires dependency '{dep}' which is not available"
                )

        return errors

    def _check_conflicts(self, module: Dict, all_modules: Set[str]) -> List[str]:
        """Check for conflicting modules."""
        errors = []
        conflicts = module.get("conflicts_with", [])

        for conflict in conflicts:
            if conflict in all_modules:
                conflict_module = self.modules_catalog.get(conflict)
                conflict_name = conflict_module["name"] if conflict_module else conflict
                errors.append(
                    f"Module '{module['name']}' conflicts with '{conflict_name}'"
                )

        return errors

    def _check_license(self, module: Dict, user_license: str) -> Dict[str, List[str]]:
        """Check license compatibility using configured hierarchy."""
        errors = []
        warnings = []

        module_license = module.get("license", "standard")

        # Use configured license hierarchy
        module_level = self.config.license_hierarchy.get(module_license, 1)
        user_level = self.config.license_hierarchy.get(user_license.lower(), 1)

        if module_level > user_level:
            errors.append(
                f"Module '{module['name']}' requires '{module_license}' license, "
                f"but user has '{user_license}' license"
            )
        elif (
            module_level < user_level
            and module_license == "free"
            and self.config.validation_settings.get(
                "warn_on_free_tier_with_premium_license", True
            )
        ):
            warnings.append(
                f"Module '{module['name']}' is free tier, consider premium alternative"
            )

        return {"errors": errors, "warnings": warnings}

    def _check_scale(self, module: Dict, user_scale: str) -> Dict[str, List[str]]:
        """Check scale compatibility - data-driven, no hardcoding."""
        errors = []
        warnings = []

        supported_scales = module.get("scale", [])
        if not supported_scales:
            # No scale restrictions defined in module
            return {"errors": errors, "warnings": warnings}

        # Normalize both user input and module scales
        user_scale_normalized = self._normalize_scale_value(user_scale)
        module_scales_normalized = [
            self._normalize_scale_value(s) for s in supported_scales
        ]

        # Check if user scale matches any supported scale
        if user_scale_normalized not in module_scales_normalized:
            errors.append(
                f"Module '{module['name']}' does not support '{user_scale}' scale. "
                f"Supported: {', '.join(supported_scales)}"
            )

        return {"errors": errors, "warnings": warnings}

    def _check_theme_coherence(self, module_ids: List[str]) -> List[str]:
        """Check if modules form coherent theme groups."""
        warnings = []

        min_modules = self.config.validation_settings.get(
            "min_modules_for_theme_check", 3
        )
        max_fragmentation = self.config.validation_settings.get(
            "max_theme_fragmentation", 2
        )

        if len(module_ids) < 2:
            return warnings

        # Count themes
        theme_counts = {}
        for module_id in module_ids:
            module = self.modules_catalog.get(module_id)
            if module:
                theme = module.get("theme", "unknown")
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Warn if too fragmented (many themes with single modules)
        single_module_themes = [t for t, c in theme_counts.items() if c == 1]
        if (
            len(single_module_themes) > max_fragmentation
            and len(module_ids) > min_modules
        ):
            warnings.append(
                f"Recommendation spans many themes ({len(theme_counts)}). "
                f"Consider focusing on fewer themes for better integration."
            )

        return warnings

    def get_missing_dependencies(self, module_ids: List[str]) -> Dict[str, List[str]]:
        """
        Get missing dependencies for each module.

        Args:
            module_ids: List of module IDs

        Returns:
            Dict mapping module_id to list of missing dependencies
        """
        all_modules = set(module_ids)
        missing = {}

        for module_id in module_ids:
            module = self.modules_catalog.get(module_id)
            if not module:
                continue

            dependencies = module.get("dependencies", [])
            missing_deps = [dep for dep in dependencies if dep not in all_modules]

            if missing_deps:
                missing[module_id] = missing_deps

        return missing

    def suggest_complementary_modules(
        self, module_ids: List[str], max_suggestions: int = 3
    ) -> List[Dict]:
        """
        Suggest complementary modules based on selected modules.

        Args:
            module_ids: Currently selected module IDs
            max_suggestions: Maximum suggestions to return

        Returns:
            List of suggested module dicts with rationale
        """
        suggestions = []
        selected_modules = {
            m_id: self.modules_catalog[m_id]
            for m_id in module_ids
            if m_id in self.modules_catalog
        }

        # Find modules with same theme but not selected
        selected_themes = {m.get("theme") for m in selected_modules.values()}

        for module in self.modules_catalog.values():
            if module["id"] in module_ids:
                continue

            # Check if module complements selected ones
            module_theme = module.get("theme")

            # Suggestion 1: Same theme modules
            if module_theme in selected_themes:
                suggestions.append(
                    {
                        "module": module,
                        "rationale": f"Complements other {module_theme} modules",
                        "score": 0.8,
                    }
                )

            # Suggestion 2: Common dependencies
            module_deps = set(module.get("dependencies", []))
            if module_deps & set(module_ids):
                suggestions.append(
                    {
                        "module": module,
                        "rationale": "Shares infrastructure dependencies",
                        "score": 0.7,
                    }
                )

        # Sort by score and deduplicate
        seen = set()
        unique_suggestions = []
        for sug in sorted(suggestions, key=lambda x: x["score"], reverse=True):
            if sug["module"]["id"] not in seen:
                unique_suggestions.append(sug)
                seen.add(sug["module"]["id"])

        return unique_suggestions[:max_suggestions]
