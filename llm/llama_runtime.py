from llama_cpp import Llama

from llm.base import BaseLLM
from llama_cpp import llama_cpp
print("Supports GPU offload:", llama_cpp.llama_supports_gpu_offload())

class LlamaRuntime(BaseLLM):


    def __init__(
        self,
        model_path: str,
        context_size: int = 8192,
        gpu_layers: int = 0,
        temperature: float = 0.7
    ):

        self.model_path = model_path
        self.context_size = context_size
        self.gpu_layers = gpu_layers
        self.temperature = temperature

        print(
            f"Loading model: {model_path}"
        )

        print(
            f"Context size: {context_size}"
        )

        print(
            f"GPU layers: {gpu_layers}"
        )

        self.llm = Llama(
            model_path=model_path,

            n_ctx=context_size,

            n_gpu_layers=gpu_layers,

            verbose=False
        )

        print("Model loaded.")

    # -----------------------------------------------------
    # Complete generation
    # -----------------------------------------------------

    def generate(self, messages):

        result = (
            self.llm.create_chat_completion(
                messages=messages,

                temperature=self.temperature,

                stream=False
            )
        )

        return (
            result["choices"][0]
            ["message"]
            ["content"]
        )

    # -----------------------------------------------------
    # Streaming generation
    # -----------------------------------------------------

    def stream(self, messages):

        stream = (
            self.llm.create_chat_completion(
                messages=messages,

                temperature=self.temperature,

                stream=True
            )
        )

        for chunk in stream:

            choices = chunk.get(
                "choices",
                []
            )

            if not choices:
                continue

            delta = choices[0].get(
                "delta",
                {}
            )

            content = delta.get(
                "content"
            )

            if content:
                yield content