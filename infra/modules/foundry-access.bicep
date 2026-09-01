param foundryProjectResourceId string
param principalId string

var segments = split(foundryProjectResourceId, '/')
var accountName = segments[8]
var projectName = segments[10]

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  name: '${accountName}/${projectName}'
}

resource userAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, principalId, 'Azure AI User')
  scope: project
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}
