// Azure Bicep — main orchestrator
// Accepts environment parameter to select dev vs prod tiers

targetScope = 'resourceGroup'

@allowed(['dev', 'prod'])
param environment string = 'dev'

param location string = resourceGroup().location

// Module deployments will be added as infrastructure is provisioned
