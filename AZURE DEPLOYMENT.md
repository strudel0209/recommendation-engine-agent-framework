# Azure Deployment Guide

This guide walks you through deploying the recommendation system to Azure using Azure Container Apps.

## Prerequisites

- Azure subscription
- Azure CLI installed and logged in (`az login`)
- Docker installed (for local testing)
- All Azure resources created (see below)

## 1. Create Azure Resources

### 1.1 Resource Group
```bash
az group create \
  --name rg-eliona-recommendation \
  --location eastus
```

### 1.2 Azure Cosmos DB
```bash
az cosmosdb create \
  --name cosmos-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --default-consistency-level Session \
  --locations regionName=eastus failoverPriority=0 isZoneRedundant=False
```

### 1.3 Azure AI Search
```bash
az search service create \
  --name search-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --sku standard \
  --location eastus
```

### 1.4 Azure OpenAI
```bash
# Create OpenAI resource
az cognitiveservices account create \
  --name openai-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --kind OpenAI \
  --sku S0 \
  --location eastus

# Deploy embedding model
az cognitiveservices account deployment create \
  --name openai-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --deployment-name text-embedding-3-large \
  --model-name text-embedding-3-large \
  --model-version "1" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "Standard"

# Deploy chat model
az cognitiveservices account deployment create \
  --name openai-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-05-13" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "Standard"
```

### 1.5 Azure AI Foundry Project
```bash
# Create AI Foundry project via portal or SDK
# Note: CLI support may vary, use Azure Portal for full setup
```

## 2. Configure Managed Identity

### 2.1 Create User-Assigned Managed Identity
```bash
az identity create \
  --name id-eliona-recommendation \
  --resource-group rg-eliona-recommendation
```

### 2.2 Get Identity Details
```bash
IDENTITY_ID=$(az identity show \
  --name id-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --query id -o tsv)

IDENTITY_PRINCIPAL_ID=$(az identity show \
  --name id-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --query principalId -o tsv)
```

### 2.3 Assign Roles to Identity

```bash
# Cosmos DB Data Contributor
az cosmosdb sql role assignment create \
  --account-name cosmos-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --role-definition-id 00000000-0000-0000-0000-000000000002 \
  --principal-id $IDENTITY_PRINCIPAL_ID \
  --scope "/dbs/eliona-catalog"

# Search Index Data Contributor
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL_ID \
  --role "Search Index Data Contributor" \
  --scope /subscriptions/{subscription-id}/resourceGroups/rg-eliona-recommendation/providers/Microsoft.Search/searchServices/search-eliona-recommendation

# Cognitive Services OpenAI User
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL_ID \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/{subscription-id}/resourceGroups/rg-eliona-recommendation/providers/Microsoft.CognitiveServices/accounts/openai-eliona-recommendation
```

## 3. Build and Push Container Image

### 3.1 Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 Create Azure Container Registry
```bash
az acr create \
  --name acrelionarecommendation \
  --resource-group rg-eliona-recommendation \
  --sku Basic \
  --admin-enabled true
```

### 3.3 Build and Push Image
```bash
# Login to ACR
az acr login --name acrelionarecommendation

# Build image
docker build -t eliona-recommendation:latest .

# Tag image
docker tag eliona-recommendation:latest acrelionarecommendation.azurecr.io/eliona-recommendation:latest

# Push image
docker push acrelionarecommendation.azurecr.io/eliona-recommendation:latest
```

## 4. Deploy to Azure Container Apps

### 4.1 Create Container Apps Environment
```bash
az containerapp env create \
  --name env-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --location eastus
```

### 4.2 Deploy Container App
```bash
az containerapp create \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --environment env-eliona-recommendation \
  --image acrelionarecommendation.azurecr.io/eliona-recommendation:latest \
  --target-port 8000 \
  --ingress external \
  --registry-server acrelionarecommendation.azurecr.io \
  --user-assigned $IDENTITY_ID \
  --env-vars \
    AZURE_COSMOS_ENDPOINT=https://cosmos-eliona-recommendation.documents.azure.com:443/ \
    AZURE_COSMOS_DATABASE=eliona-catalog \
    AZURE_COSMOS_CONTAINER_MODULES=modules \
    AZURE_COSMOS_CONTAINER_INTERACTIONS=interactions \
    AZURE_SEARCH_ENDPOINT=https://search-eliona-recommendation.search.windows.net \
    AZURE_SEARCH_INDEX_NAME=eliona-modules \
    AZURE_OPENAI_ENDPOINT=https://openai-eliona-recommendation.openai.azure.com/ \
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large \
    AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o \
    AZURE_OPENAI_API_VERSION=2024-08-01-preview \
    AZURE_AI_FOUNDRY_ENDPOINT=https://your-project.api.azureml.ms
```

### 4.3 Get App URL
```bash
az containerapp show \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --query properties.configuration.ingress.fqdn -o tsv
```

## 5. Initialize Data

### 5.1 Run Setup Script Remotely
You can run the setup scripts from your local machine (they will connect to Azure):

```bash
python scripts/setup_all.py
```

Or create a one-time Container App job:

```bash
az containerapp job create \
  --name job-setup-data \
  --resource-group rg-eliona-recommendation \
  --environment env-eliona-recommendation \
  --image acrelionarecommendation.azurecr.io/eliona-recommendation:latest \
  --user-assigned $IDENTITY_ID \
  --trigger-type Manual \
  --replica-timeout 1800 \
  --command "python" "scripts/setup_all.py"

# Execute the job
az containerapp job start \
  --name job-setup-data \
  --resource-group rg-eliona-recommendation
```

## 6. Verify Deployment

### 6.1 Test Health Endpoint
```bash
APP_URL=$(az containerapp show \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --query properties.configuration.ingress.fqdn -o tsv)

curl https://$APP_URL/health
```

### 6.2 Test Recommendation
```bash
curl -X POST https://$APP_URL/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "query": "reduce energy costs",
    "user_id": "test_user",
    "user_context": {"building_scale": "medium"}
  }'
```

## 7. Configure Custom Domain (Optional)

### 7.1 Add Custom Domain
```bash
az containerapp hostname add \
  --hostname api.eliona.io \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation
```

### 7.2 Bind Certificate
```bash
az containerapp hostname bind \
  --hostname api.eliona.io \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --environment env-eliona-recommendation \
  --validation-method CNAME
```

## 8. Enable Monitoring

### 8.1 Create Log Analytics Workspace
```bash
az monitor log-analytics workspace create \
  --workspace-name log-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --location eastus
```

### 8.2 Enable Application Insights
```bash
az monitor app-insights component create \
  --app insights-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --location eastus \
  --workspace log-eliona-recommendation
```

### 8.3 Update Container App with Insights
```bash
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app insights-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --query instrumentationKey -o tsv)

az containerapp update \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING=$INSTRUMENTATION_KEY
```

## 9. Scaling Configuration

### 9.1 Configure Autoscaling
```bash
az containerapp update \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --min-replicas 1 \
  --max-replicas 10 \
  --scale-rule-name http-rule \
  --scale-rule-type http \
  --scale-rule-http-concurrency 10
```

## 10. Continuous Deployment (GitHub Actions)

### 10.1 Create Service Principal
```bash
az ad sp create-for-rbac \
  --name sp-eliona-recommendation \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/rg-eliona-recommendation \
  --sdk-auth
```

Save the output JSON as a GitHub secret named `AZURE_CREDENTIALS`.

### 10.2 Create GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Azure Login
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Build and Push to ACR
      run: |
        az acr login --name acrelionarecommendation
        docker build -t acrelionarecommendation.azurecr.io/eliona-recommendation:${{ github.sha }} .
        docker push acrelionarecommendation.azurecr.io/eliona-recommendation:${{ github.sha }}
    
    - name: Deploy to Container Apps
      run: |
        az containerapp update \
          --name app-eliona-recommendation \
          --resource-group rg-eliona-recommendation \
          --image acrelionarecommendation.azurecr.io/eliona-recommendation:${{ github.sha }}
```

## 11. Security Best Practices

### 11.1 Network Security
```bash
# Restrict Container Apps to VNet
az containerapp env create \
  --name env-eliona-recommendation-secure \
  --resource-group rg-eliona-recommendation \
  --location eastus \
  --internal-only true
```

### 11.2 Enable Azure Private Link
```bash
# For Cosmos DB
az cosmosdb private-endpoint-connection approve \
  --account-name cosmos-eliona-recommendation \
  --resource-group rg-eliona-recommendation
```

### 11.3 Configure API Management (Optional)
Use Azure API Management for:
- Rate limiting
- Authentication
- API key management
- Request throttling

## 12. Cost Optimization

### Tips for MVP/Development:
- Use serverless Cosmos DB (consumption-based)
- Start with Basic AI Search tier
- Use Container Apps consumption plan
- Scale down during off-hours

### Production Recommendations:
- Reserved capacity for Cosmos DB
- Standard AI Search tier with autoscale
- Container Apps dedicated plan for predictable costs
- Azure Front Door for global distribution

## 13. Maintenance

### Update Application
```bash
# Build new version
docker build -t acrelionarecommendation.azurecr.io/eliona-recommendation:v2 .
docker push acrelionarecommendation.azurecr.io/eliona-recommendation:v2

# Deploy update
az containerapp update \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --image acrelionarecommendation.azurecr.io/eliona-recommendation:v2
```

### View Logs
```bash
az containerapp logs show \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --follow
```

### Scale Manually
```bash
az containerapp update \
  --name app-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --min-replicas 2 \
  --max-replicas 5
```

## 14. Disaster Recovery

### Backup Strategy:
1. **Cosmos DB**: Enable continuous backup
2. **AI Search**: Export index definitions and data
3. **Container Images**: Keep multiple versions in ACR
4. **Configuration**: Store in Azure App Configuration

### Enable Cosmos DB Backup:
```bash
az cosmosdb update \
  --name cosmos-eliona-recommendation \
  --resource-group rg-eliona-recommendation \
  --backup-policy-type Continuous
```

## Support

For issues, check:
- Container Apps logs: `az containerapp logs show`
- Application Insights metrics
- Azure Service Health
- GitHub Issues (if open source)

---

**Deployment Checklist:**
- [ ] All Azure resources created
- [ ] Managed identity configured with proper roles
- [ ] Container image built and pushed to ACR
- [ ] Container App deployed and running
- [ ] Data initialized (setup scripts run)
- [ ] Health endpoint returns 200 OK
- [ ] Test recommendation request succeeds
- [ ] Monitoring enabled
- [ ] Autoscaling configured
- [ ] Documentation updated with production URLs
