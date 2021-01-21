import os

from mlmodule.contrib.resnet import ResNetFeatures
from mlmodule.torch.data.images import ImageFilesDatasets
from mlmodule.utils import list_files_in_dir


def test_resnet_features_inference():
    resnet = ResNetFeatures("resnet18")
    # Pretrained model
    resnet.load()
    base_path = os.path.join("mlmodule", "tests", "fixtures", "cats_dogs")
    file_names = list_files_in_dir(base_path, allowed_extensions=('jpg',))[:50]
    dataset = ImageFilesDatasets(file_names)

    features = resnet.bulk_inference(dataset, batch_size=10)
    assert len(features) == 50
    assert len(features[0]) == 512
