targetScope = 'subscription'

@minLength(1)
param environmentName string
param location string
param subscriptionId string
param tenantId string
param resourceGroupName string
@minLength(2)
@maxLength(32)
param containerAppName string
param sharedResourceGroupName string
param sharedContainerAppsEnvironmentName string
param sharedRegistryName string
param sharedLogAnalyticsWorkspaceName string
@minValue(0)
@maxValue(1)
param minReplicas int = 0
param bootstrapMode bool = true
param imageName string = ''
param foundryProjectResourceId string = ''
param apiClientId string
param alexObjectId string
param fabricSqlServer string
param fabricSqlDatabase string
param workIqSupplierSourceId string
param workIqQualitySourceId string
param workIqCorpusVersion string
param workIqDeploymentReceipt string
param tenantSharePointHost string
param foundryProjectEndpoint string
param foundrySignalAgentName string
param foundrySignalAgentVersion string
param foundryContextAgentName string
param foundryContextAgentVersion string
param foundryDecisionAgentName string
param foundryDecisionAgentVersion string
param foundryDeploymentReceipt string
param powerBiReportUrl string
param powerBiDeploymentReceipt string
param fabricCitationBaseUrl string

var tags = {
  'azd-env-name': environmentName
  application: 'supply-response'
  environment: environmentName
}

// Bicep has no stable regex decorator. Invalid consecutive hyphens become an
// empty module parameter, which the nested template's minLength rejects.
var validatedContainerAppName = contains(containerAppName, '--') ? '' : containerAppName

resource applicationResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: applicationResourceGroup
  params: {
    applicationInsightsName: 'appi-supply-response-${environmentName}'
    location: location
    sharedSubscriptionId: subscriptionId
    sharedResourceGroupName: sharedResourceGroupName
    sharedWorkspaceName: sharedLogAnalyticsWorkspaceName
    tags: tags
  }
}

module vault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  scope: applicationResourceGroup
  params: {
    vaultName: 'kv-sr-${uniqueString(subscriptionId, environmentName)}'
    location: location
    tenantId: tenantId
    tags: tags
  }
}

module app 'modules/container-apps.bicep' = {
  name: 'container-app'
  scope: applicationResourceGroup
  params: {
    appName: validatedContainerAppName
    sharedSubscriptionId: subscriptionId
    sharedResourceGroupName: sharedResourceGroupName
    sharedEnvironmentName: sharedContainerAppsEnvironmentName
    minReplicas: minReplicas
    bootstrapMode: bootstrapMode
    imageName: imageName
    registryServer: '${sharedRegistryName}.azurecr.io'
    keyVaultUri: vault.outputs.vaultUri
    applicationInsightsConnectionString: monitoring.outputs.connectionString
    tenantId: tenantId
    runtimeSettings: {
      apiClientId: apiClientId
      alexObjectId: alexObjectId
      fabricSqlServer: fabricSqlServer
      fabricSqlDatabase: fabricSqlDatabase
      workIqSupplierSourceId: workIqSupplierSourceId
      workIqQualitySourceId: workIqQualitySourceId
      workIqCorpusVersion: workIqCorpusVersion
      workIqDeploymentReceipt: workIqDeploymentReceipt
      tenantSharePointHost: tenantSharePointHost
      foundryProjectEndpoint: foundryProjectEndpoint
      foundrySignalAgentName: foundrySignalAgentName
      foundrySignalAgentVersion: foundrySignalAgentVersion
      foundryContextAgentName: foundryContextAgentName
      foundryContextAgentVersion: foundryContextAgentVersion
      foundryDecisionAgentName: foundryDecisionAgentName
      foundryDecisionAgentVersion: foundryDecisionAgentVersion
      foundryDeploymentReceipt: foundryDeploymentReceipt
      powerBiReportUrl: powerBiReportUrl
      powerBiDeploymentReceipt: powerBiDeploymentReceipt
      fabricCitationBaseUrl: fabricCitationBaseUrl
    }
    tags: union(tags, { 'azd-service-name': 'api' })
  }
}

module registryAccess 'modules/registry.bicep' = {
  name: 'registry-access'
  scope: resourceGroup(subscriptionId, sharedResourceGroupName)
  params: {
    registryName: sharedRegistryName
    principalId: app.outputs.principalId
  }
}

module vaultAccess 'modules/rbac.bicep' = {
  name: 'vault-access'
  scope: applicationResourceGroup
  params: {
    principalId: app.outputs.principalId
    targetResourceName: vault.outputs.vaultName
    roleDefinitionId: '4633458b-17de-408a-b874-0445c86b69e6'
  }
}

module foundryAccess 'modules/foundry-access.bicep' = if (!empty(foundryProjectResourceId)) {
  name: 'foundry-access'
  scope: resourceGroup(subscriptionId, split(foundryProjectResourceId, '/')[4])
  params: {
    foundryProjectResourceId: foundryProjectResourceId
    principalId: app.outputs.principalId
  }
}

output AZURE_RESOURCE_GROUP string = applicationResourceGroup.name
output AZURE_LOCATION string = location
output SERVICE_API_NAME string = app.outputs.appName
output SERVICE_API_URI string = 'https://${app.outputs.fqdn}'
output SUPPLY_RESPONSE_KEY_VAULT_NAME string = vault.outputs.vaultName
output SUPPLY_RESPONSE_APPLICATION_INSIGHTS_CONNECTION_STRING string = monitoring.outputs.connectionString
output SUPPLY_RESPONSE_ACR_LOGIN_SERVER string = registryAccess.outputs.loginServer
