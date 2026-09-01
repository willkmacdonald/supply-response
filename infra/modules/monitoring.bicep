param applicationInsightsName string
param location string
param sharedSubscriptionId string
param sharedResourceGroupName string
param sharedWorkspaceName string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  scope: resourceGroup(sharedSubscriptionId, sharedResourceGroupName)
  name: sharedWorkspaceName
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output connectionString string = insights.properties.ConnectionString
