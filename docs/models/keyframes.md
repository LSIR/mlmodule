# Video key-frames extractor

This model implements two types of modules: a video frames encoder and the key-frames module.
These models are an implementation of a [`TorchMlModule`][mlmodule.torch.modules.TorchMlModule].

## Pre-trained models

{% for model in models.keyframes -%}
::: mlmodule.models.keyframes.{{ model.factory }}
    rendering:
        show_signature: False
{% endfor %}


## Base key-frames selector model

These models allow to extract key-frames from a video.

::: mlmodule.models.keyframes.selectors.KeyFrameSelector
    selection:
        members: none

## Base video frames encoder model

::: mlmodule.models.keyframes.encoders.VideoFramesEncoder
    selection:
        members: none
