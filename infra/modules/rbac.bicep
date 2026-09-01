param principalId string
@allowed([
  'User'
  'ServicePrincipal'
])
param principalType string
param targetResourceName string
param roleDefinitionId string

resource target 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: targetResourceName
}

resource assignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(target.id, principalId, roleDefinitionId)
  scope: target
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
  }
}

output assignmentId string = assignment.id
