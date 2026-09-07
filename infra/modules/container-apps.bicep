@minLength(2)
@maxLength(32)
param appName string
param sharedSubscriptionId string
param sharedResourceGroupName string
param sharedEnvironmentName string
@minValue(0)
@maxValue(1)
param minReplicas int
param bootstrapMode bool
param imageName string
param registryServer string
param keyVaultUri string
param applicationInsightsConnectionString string
param tenantId string
param runtimeSettings object
param tags object

var placeholderImage = 'mcr.microsoft.com/k8se/quickstart:latest'
var finalProbes = [
  {
    type: 'Startup'
    httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
    initialDelaySeconds: 1
    periodSeconds: 3
    failureThreshold: 30
  }
  {
    type: 'Liveness'
    httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
    periodSeconds: 30
  }
  {
    type: 'Readiness'
    httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
    periodSeconds: 10
  }
]
var finalEnvironment = [
  { name: 'SUPPLY_RESPONSE_RUNTIME_MODE', value: 'live' }
  { name: 'SUPPLY_RESPONSE_CREDENTIAL_MODE', value: 'managed_identity' }
  { name: 'SUPPLY_RESPONSE_ALLOWED_TENANT_ID', value: tenantId }
  { name: 'SUPPLY_RESPONSE_FRONTEND_ORIGIN', value: 'https://${appName}.${environment.properties.defaultDomain}' }
  { name: 'SUPPLY_RESPONSE_API_CLIENT_ID', value: runtimeSettings.apiClientId }
  { name: 'SUPPLY_RESPONSE_ALEX_OBJECT_ID', value: runtimeSettings.alexObjectId }
  { name: 'SUPPLY_RESPONSE_FABRIC_SQL_SERVER', value: runtimeSettings.fabricSqlServer }
  { name: 'SUPPLY_RESPONSE_FABRIC_SQL_DATABASE', value: runtimeSettings.fabricSqlDatabase }
  { name: 'SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SOURCE_ID', value: runtimeSettings.workIqSupplierSourceId }
  { name: 'SUPPLY_RESPONSE_WORKIQ_QUALITY_SOURCE_ID', value: runtimeSettings.workIqQualitySourceId }
  { name: 'SUPPLY_RESPONSE_WORKIQ_SUPPLIER_SENDER', value: runtimeSettings.workIqSupplierSender }
  { name: 'SUPPLY_RESPONSE_WORKIQ_QUALITY_AUTHOR_OBJECT_ID', value: runtimeSettings.workIqQualityAuthorObjectId }
  { name: 'SUPPLY_RESPONSE_WORKIQ_TEAM_ID', value: runtimeSettings.workIqTeamId }
  { name: 'SUPPLY_RESPONSE_WORKIQ_CHANNEL_ID', value: runtimeSettings.workIqChannelId }
  { name: 'SUPPLY_RESPONSE_WORKIQ_CORPUS_VERSION', value: runtimeSettings.workIqCorpusVersion }
  { name: 'SUPPLY_RESPONSE_WORKIQ_DEPLOYMENT_RECEIPT', value: runtimeSettings.workIqDeploymentReceipt }
  { name: 'SUPPLY_RESPONSE_TENANT_SHAREPOINT_HOST', value: runtimeSettings.tenantSharePointHost }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_PROJECT_ENDPOINT', value: runtimeSettings.foundryProjectEndpoint }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_NAME', value: runtimeSettings.foundrySignalAgentName }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_SIGNAL_AGENT_VERSION', value: runtimeSettings.foundrySignalAgentVersion }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_NAME', value: runtimeSettings.foundryContextAgentName }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_CONTEXT_AGENT_VERSION', value: runtimeSettings.foundryContextAgentVersion }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_NAME', value: runtimeSettings.foundryDecisionAgentName }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_DECISION_AGENT_VERSION', value: runtimeSettings.foundryDecisionAgentVersion }
  { name: 'SUPPLY_RESPONSE_FOUNDRY_DEPLOYMENT_RECEIPT', value: runtimeSettings.foundryDeploymentReceipt }
  { name: 'SUPPLY_RESPONSE_POWER_BI_REPORT_URL', value: runtimeSettings.powerBiReportUrl }
  { name: 'SUPPLY_RESPONSE_POWER_BI_DEPLOYMENT_RECEIPT', value: runtimeSettings.powerBiDeploymentReceipt }
  { name: 'SUPPLY_RESPONSE_FABRIC_CITATION_BASE_URL', value: runtimeSettings.fabricCitationBaseUrl }
  { name: 'SUPPLY_RESPONSE_ENTRA_CLIENT_SECRET', secretRef: 'entra-client-secret' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsightsConnectionString }
]

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  scope: resourceGroup(sharedSubscriptionId, sharedResourceGroupName)
  name: sharedEnvironmentName
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: resourceGroup().location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: bootstrapMode ? [] : [
        {
          server: registryServer
          identity: 'system'
        }
      ]
      secrets: bootstrapMode ? [] : [
        {
          name: 'entra-client-secret'
          keyVaultUrl: '${keyVaultUri}secrets/entra-client-secret'
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: bootstrapMode ? 80 : 8000
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'supply-response'
          image: bootstrapMode ? placeholderImage : imageName
          env: bootstrapMode ? [] : finalEnvironment
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: bootstrapMode ? [] : finalProbes
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 2
      }
    }
  }
}

output appName string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output principalId string = app.identity.principalId
