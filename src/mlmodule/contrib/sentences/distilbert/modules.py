from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Union

import requests
import torch
from tokenizers import Tokenizer

from mlmodule.contrib.sentences.distilbert.outputs import BaseModelOutput
from mlmodule.contrib.sentences.distilbert.transforms import TokenizerTransform
from mlmodule.v2.torch.modules import TorchMlModule
from mlmodule.v2.torch.utils import add_prefix_to_state_dict

from .blocks.dense import Dense
from .blocks.embeddings import Embeddings
from .blocks.pooling import Pooling
from .blocks.transformers import Transformer
from .config import DistilBertConfig


class BaseDistilBertModule(TorchMlModule):

    transformer_weights_url: str
    dense_layer_weights_url: str
    tokenizer_params_url: str

    def __init__(
        self,
        device: torch.device,
        config: DistilBertConfig,
        pooling_config: Dict[str, Any],
        dense_config: Dict[str, Any],
    ):
        self.device = device
        super().__init__()
        self.config = config

        self.embeddings = Embeddings(config)  # Embeddings
        self.transformer = Transformer(config)  # Encoder
        self.pool = Pooling(**pooling_config)
        self.dense = Dense(**dense_config)
        self._tokenizer: Optional[Tokenizer] = None

    def get_tokenizer(self) -> Tokenizer:
        """Return a tokenizer loaded once and cached on the instance"""
        if self._tokenizer is None:
            raise ValueError(
                "The model tokenizer has not been initialised, try to load the model weights first"
            )
        return self._tokenizer

    def set_state_from_provider(self) -> None:
        """Gets model weigths from HuggingFace and applies them to the current model"""
        # Loading embeddings and transformer weights
        state: OrderedDict[str, torch.Tensor] = torch.hub.load_state_dict_from_url(
            self.transformer_weights_url, map_location=self.device
        )
        # Loading dense layer weights
        dense_state = torch.hub.load_state_dict_from_url(
            self.dense_layer_weights_url, map_location=self.device
        )
        state.update(add_prefix_to_state_dict(dense_state, "dense"))
        # Loading weights
        self.load_state_dict(state)
        # Loading tokenizer
        resp = requests.get(self.tokenizer_params_url)
        if resp.status_code == 200:
            self._tokenizer = Tokenizer.from_str(resp.text)
        else:
            raise ValueError(
                f"Cannot load tokenizer configuration from {self.tokenizer_params_url}"
            )

    def get_head_mask(
        self,
        head_mask: Optional[torch.Tensor],
        num_hidden_layers: int,
        is_attention_chunked: bool = False,
    ) -> Union[torch.Tensor, List[None]]:
        """
        Prepare the head mask if needed.

        Args:
            head_mask (`torch.Tensor` with shape `[num_heads]` or `[num_hidden_layers x num_heads]`, *optional*):
                The mask indicating if we should keep the heads or not (1.0 for keep, 0.0 for discard).
            num_hidden_layers (`int`):
                The number of hidden layers in the model.
            is_attention_chunked: (`bool`, *optional*, defaults to `False`):
                Whether or not the attentions scores are computed by chunks or not.

        Returns:
            `torch.Tensor` with shape `[num_hidden_layers x batch x num_heads x seq_length x seq_length]` or
            list with `[None]` for each layer.
        """
        ret: Union[torch.Tensor, List[None]]
        if head_mask is not None:
            head_mask_5d: torch.Tensor = self._convert_head_mask_to_5d(
                head_mask, num_hidden_layers
            )
            if is_attention_chunked is True:
                ret = head_mask_5d.unsqueeze(-1)
        else:
            ret = [None] * num_hidden_layers

        return ret

    def _convert_head_mask_to_5d(self, head_mask, num_hidden_layers):
        """-> [num_hidden_layers x batch x num_heads x seq_length x seq_length]"""
        if head_mask.dim() == 1:
            head_mask = head_mask.unsqueeze(0).unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
            head_mask = head_mask.expand(num_hidden_layers, -1, -1, -1, -1)
        elif head_mask.dim() == 2:
            head_mask = (
                head_mask.unsqueeze(1).unsqueeze(-1).unsqueeze(-1)
            )  # We can specify head_mask for each layer
        assert head_mask.dim() == 5, f"head_mask.dim != 5, instead {head_mask.dim()}"
        head_mask = head_mask.to(
            dtype=self.dtype
        )  # switch to float if need + fp16 compatibility
        return head_mask

    def forward_transformer(
        self,
        input_ids=None,
        attention_mask=None,
        head_mask=None,
        inputs_embeds=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
    ) -> BaseModelOutput:
        """
        Args:
            input_ids (`torch.LongTensor` of shape `(batch_size)`):
                Indices of input sequence tokens in the vocabulary.

                Indices can be obtained using [`DistilBertTokenizer`]. See
                [`PreTrainedTokenizer.encode`] and [`PreTrainedTokenizer.__call__`] for
                details.

                [What are input IDs?](../glossary#input-ids)
            attention_mask (`torch.FloatTensor` of shape `(batch_size)`, *optional*):
                Mask to avoid performing attention on padding token indices. Mask values selected in `[0, 1]`:

                - 1 for tokens that are **not masked**,
                - 0 for tokens that are **masked**.

                [What are attention masks?](../glossary#attention-mask)
            head_mask (`torch.FloatTensor` of shape `(num_heads,)` or `(num_layers, num_heads)`, *optional*):
                Mask to nullify selected heads of the self-attention modules. Mask values selected in `[0, 1]`:

                - 1 indicates the head is **not masked**,
                - 0 indicates the head is **masked**.

            inputs_embeds (`torch.FloatTensor` of shape `(batch_size, hidden_size)`, *optional*):
                Optionally, instead of passing `input_ids` you can choose to directly pass an embedded representation.
                This is useful if you want more control over how to convert `input_ids` indices into associated
                vectors than the model's internal embedding lookup matrix.
            output_attentions (`bool`, *optional*):
                Whether or not to return the attentions tensors of all attention layers.
                See `attentions` under returned tensors for more detail.
            output_hidden_states (`bool`, *optional*):
                Whether or not to return the hidden states of all layers.
                See `hidden_states` under returned tensors for more detail.
            return_dict (`bool`, *optional*):
                Whether or not to return a [`~file_utils.ModelOutput`] instead of a plain tuple.
        """
        output_attentions = (
            output_attentions
            if output_attentions is not None
            else self.config.output_attentions
        )
        output_hidden_states = (
            output_hidden_states
            if output_hidden_states is not None
            else self.config.output_hidden_states
        )
        return_dict = (
            return_dict if return_dict is not None else self.config.use_return_dict
        )

        if input_ids is not None and inputs_embeds is not None:
            raise ValueError(
                "You cannot specify both input_ids and inputs_embeds at the same time"
            )
        elif input_ids is not None:
            input_shape = input_ids.size()
        elif inputs_embeds is not None:
            input_shape = inputs_embeds.size()[:-1]
        else:
            raise ValueError("You have to specify either input_ids or inputs_embeds")

        device = input_ids.device if input_ids is not None else inputs_embeds.device

        if attention_mask is None:
            attention_mask = torch.ones(input_shape, device=device)  # (bs, seq_length)

        # Prepare head mask if needed
        head_mask = self.get_head_mask(head_mask, self.config.num_hidden_layers)

        if inputs_embeds is None:
            inputs_embeds = self.embeddings(input_ids)  # (bs, seq_length, dim)
        return self.transformer(
            x=inputs_embeds,
            attn_mask=attention_mask,
            head_mask=head_mask,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

    def forward(
        self, input_ids: torch.IntTensor, attention_mask: torch.IntTensor
    ) -> torch.Tensor:
        output_tokens, _ = self.forward_transformer(
            input_ids, attention_mask, return_dict=False
        )
        features = self.pool.forward(
            {"token_embeddings": output_tokens, "attention_mask": attention_mask}
        )
        return self.dense.forward(features)["sentence_embedding"]

    def get_dataset_transforms(self) -> List[Callable]:
        return [TokenizerTransform(self.get_tokenizer())]


class DistilUseBaseMultilingualCasedV2Module(BaseDistilBertModule):

    transformer_weights_url: str = (
        "https://cdn-lfs.huggingface.co"
        "/sentence-transformers/distiluse-base-multilingual-cased-v2"
        "/0ea26561995c7c873e177e6801bb80f36511281d4d96c0f62aea6c19e85ddb7b"
    )
    dense_layer_weights_url: str = (
        "https://cdn-lfs.huggingface.co"
        "/sentence-transformers/distiluse-base-multilingual-cased-v2"
        "/64fe81485f483cee6c54573686e4117a9e6f32e1579022d3621a1487d5bfea58"
    )
    tokenizer_params_url: str = (
        "https://huggingface.co"
        "/sentence-transformers/distiluse-base-multilingual-cased-v2/raw/main/tokenizer.json"
    )

    def __init__(self, device: torch.device):
        config = DistilBertConfig(
            vocab_size=119547,
            activation="gelu",
            attention_dropout=0.1,
            dim=768,
            dropout=0.1,
            hidden_dim=3072,
            initializer_range=0.02,
            max_position_embeddings=512,
            n_heads=12,
            n_layers=6,
            output_hidden_states=True,
            output_past=True,
            pad_token_id=0,
            qa_dropout=0.1,
            seq_classif_dropout=0.2,
            sinusoidal_pos_embds=False,
            tie_weights_=True,
        )
        pooling_config = {
            "word_embedding_dimension": 768,
            "pooling_mode_cls_token": False,
            "pooling_mode_mean_tokens": True,
            "pooling_mode_max_tokens": False,
            "pooling_mode_mean_sqrt_len_tokens": False,
        }
        dense_config = {
            "in_features": 768,
            "out_features": 512,
            "bias": True,
            "activation_function": torch.nn.Tanh(),
        }
        super().__init__(device, config, pooling_config, dense_config)
