from prefect.infrastructure import Process, DockerContainer
from prefect_azure import AzureContainerInstanceJob
from prefect.blocks.core import Block
from typing import Optional
import os

class GPUContainerInstanceJob(AzureContainerInstanceJob):
    """Custom Azure Container Instance block with GPU support"""
    
    gpu_count: int = 1
    gpu_sku: str = "K80"  # or "P100", "V100"
    
    def _prepare_container_group(self):
        container_group = super()._prepare_container_group()
        
        # Add GPU configuration
        container_group["properties"]["containers"][0]["resources"]["requests"]["gpu"] = {
            "count": self.gpu_count,
            "sku": self.gpu_sku
        }
        
        return container_group

# Register infrastructure blocks
async def setup_infrastructure_blocks():
    # CPU Worker Infrastructure
    cpu_process = Process(
        name="cpu-worker-process",
        working_dir="/opt/fon-aios",
        env={
            "PREFECT_API_URL": os.getenv("PREFECT_API_URL"),
            "PREFECT_API_KEY": os.getenv("PREFECT_API_KEY")
        }
    )
    await cpu_process.save("cpu-worker-infra", overwrite=True)
    
    # GPU Container Infrastructure for Azure
    gpu_container = GPUContainerInstanceJob(
        name="gpu-nlp-processor",
        resource_group_name="fon-aios-rg",
        subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
        image="fonregistry.azurecr.io/nlp-langchain-gpu:latest",
        cpu=4,
        memory=16,
        gpu_count=1,
        gpu_sku="K80",
        env_vars={
            "TRANSFORMERS_CACHE": "/models",
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": os.getenv("LANGCHAIN_API_KEY")
        },
        command=["python", "-m", "prefect.engine"]
    )
    await gpu_container.save("gpu-nlp-infra", overwrite=True)

# Register the custom block
if __name__ == "__main__":
    import asyncio
    asyncio.run(setup_infrastructure_blocks())