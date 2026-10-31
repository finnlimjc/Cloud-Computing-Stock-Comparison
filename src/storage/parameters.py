import logging
import os
import boto3
from botocore.utils import InstanceMetadataRegionFetcher

LOGGER = logging.getLogger(__name__)

def use_instance_region() -> None:
    """Make boto3 use the EC2 instance's Region, unless AWS_DEFAULT_REGION or ~/.aws/config already sets one."""
    if boto3.Session().region_name:
        return
    region = InstanceMetadataRegionFetcher().retrieve_region() #boto3 does not read the Region from instance metadata itself
    if region is None:
        raise ValueError("No AWS Region found: set AWS_DEFAULT_REGION, or run on EC2 where the instance metadata provides it.")
    boto3.setup_default_session(region_name=region)

class ParameterStore:
    """
    Settings and secrets in AWS Systems Manager Parameter Store, read with the EC2 instance role.
    
    Inputs:
    - client: boto3 SSM client, or None to create one from the instance's region and credentials
    """
    
    def __init__(self, client:object=None) -> None:
        self.client = client or boto3.client("ssm")
    
    def get_many(self, names:list[str]) -> dict[str, str]:
        """Read and decrypt parameters, raising ValueError that lists every name not found.
        
        Inputs:
        - names: parameter names, at most 10 (the GetParameters limit)
        
        Outputs:
        - Parameter values by name
        """
        response = self.client.get_parameters(Names=names, WithDecryption=True)
        if response["InvalidParameters"]:
            raise ValueError(f"Missing parameters in Parameter Store: {', '.join(response['InvalidParameters'])}")
        return {parameter["Name"]: parameter["Value"] for parameter in response["Parameters"]}
    
    def put_secret(self, name:str, value:str) -> None:
        """Save a value as an encrypted SecureString, replacing any older value under the same name."""
        self.client.put_parameter(Name=name, Value=value, Type="SecureString", Overwrite=True)
    
    def export_to_environment(self, variables:dict[str, str]) -> None:
        """Copy parameters into environment variables that are not set yet, logging any parameter that is missing.
        
        Inputs:
        - variables: environment variable name -> parameter name
        """
        response = self.client.get_parameters(Names=list(variables.values()), WithDecryption=True)
        values = {parameter["Name"]: parameter["Value"] for parameter in response["Parameters"]}
        for variable, name in variables.items():
            if name in values:
                os.environ.setdefault(variable, values[name])
            else:
                LOGGER.warning("Parameter %s not found; %s stays unset.", name, variable)
