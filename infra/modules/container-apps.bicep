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
