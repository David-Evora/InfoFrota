"""LLM local em processo (transformers + peft), para avaliar o LoRA direto no Kaggle.
Uso: --provider hf --model unsloth/Llama-3.1-8B-Instruct::/kaggle/working/lora
(sem '::adaptador' avalia o modelo base)."""


class HFLLM:
    def __init__(self, base, adapter=None, max_new_tokens=400, quatro_bits=True):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self.nome = base.split("/")[-1] + ("+lora" if adapter else "")
        self.tok = AutoTokenizer.from_pretrained(base)
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_compute_dtype=torch.float16) if quatro_bits else None
        self.model = AutoModelForCausalLM.from_pretrained(
            base, quantization_config=q, device_map={"": 0}, torch_dtype=torch.float16)
        if adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter)
        self.model.eval()
        self.max_new_tokens = max_new_tokens

    def complete(self, system, messages):
        import torch
        msgs = [{"role": "system", "content": system}] + list(messages)
        # mesma tokenização do treino (texto -> ids); evita o BatchEncoding das versões novas
        texto = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        ids = self.tok(texto, add_special_tokens=False, return_tensors="pt")["input_ids"].to(0)
        with torch.no_grad():
            out = self.model.generate(ids, max_new_tokens=self.max_new_tokens, do_sample=False,
                                      pad_token_id=self.tok.eos_token_id)
        return self.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)
