from mlmodule.contrib.vinvl.models.structures.image_list import to_image_list


class BatchCollator(object):
    """
    From a list of samples from the dataset,
    returns the batched images and targets.
    This should be passed to the DataLoader
    """

    def __init__(self, size_divisible=0):
        self.size_divisible = size_divisible

    def __call__(self, batch):
        transposed_batch = list(zip(*batch))
        paths = transposed_batch[0]
        images = to_image_list(transposed_batch[1], self.size_divisible)
        sizes = transposed_batch[2]
        return paths, images, sizes
