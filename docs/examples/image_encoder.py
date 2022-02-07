from mlmodule.contrib.resnet import TorchResNetModule
from mlmodule.v2.helpers.callbacks import CollectFeaturesInMemory
from mlmodule.v2.stores import MLModuleModelStore
from mlmodule.v2.torch.datasets import OpenImageFileDataset
from mlmodule.v2.torch.options import TorchRunnerOptions
from mlmodule.v2.torch.runners import TorchInferenceRunner

# Getting a dataset of images
dataset = OpenImageFileDataset(
    paths=["tests/fixtures/cats_dogs/cat_0.jpg", "tests/fixtures/cats_dogs/cat_90.jpg"]
)

# Getting pretrained model
store = MLModuleModelStore()
resnet = TorchResNetModule("resnet18")
store.load(resnet)

# Creating the callback to collect data
features = CollectFeaturesInMemory()

# Getting the torch runner for inference
runner = TorchInferenceRunner(
    model=resnet,
    dataset=dataset,
    callbacks=[features],
    options=TorchRunnerOptions(tqdm_enabled=True),
)

# Executing inference
runner.run()

# Printing the features
print(features.indices, features.features)
