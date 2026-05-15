"""
LoRA 微调脚本 — 可用 Colab 免费 T4 运行
基于 Unsloth 加速，约 30-60 分钟完成训练

使用方法:
  1. pip install unsloth
  2. python finetune.py
  3. 将输出的 GGUF 文件导入 Ollama

也可以在 Colab 直接运行:
  https://colab.research.google.com/
  选择 T4 GPU，粘贴此脚本即可
"""
import json
import os

# 训练配置
BASE_MODEL = "unsloth/qwen2.5-7b"       # 基座模型
OUTPUT_DIR = "./route-planner-lora"       # LoRA 权重输出
GGUF_OUTPUT = "./route-planner.Q4_K_M.gguf"  # 量化模型输出
TRAINING_DATA = "./training_data_alpaca.json"

LORA_R = 16          # LoRA rank
LORA_ALPHA = 32
EPOCHS = 3
LEARNING_RATE = 2e-4
MAX_SEQ_LENGTH = 2048


def load_training_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_alpaca(sample):
    """Alpaca 格式 → 标准 prompt 模板"""
    inst = sample.get("instruction", "")
    inp = sample.get("input", "")
    out = sample.get("output", "")

    if inp:
        prompt = f"""<|im_start|>system
你是 LocalSmartRoute，专精于本地路线规划的 AI 助手。
<|im_end|>
<|im_start|>user
{inst}

{inp}
<|im_end|>
<|im_start|>assistant
{out}
<|im_end|>"""
    else:
        prompt = f"""<|im_start|>system
你是 LocalSmartRoute，专精于本地路线规划的 AI 助手。
<|im_end|>
<|im_start|>user
{inst}
<|im_end|>
<|im_start|>assistant
{out}
<|im_end|>"""
    return prompt


def run_finetune():
    print("=" * 50)
    print("LocalSmartRoute LoRA Fine-tuning")
    print("=" * 50)

    # 检查训练数据
    if not os.path.exists(TRAINING_DATA):
        print(f"❌ 训练数据不存在: {TRAINING_DATA}")
        print("   请先运行: python generate_training_data.py")
        return

    samples = load_training_data(TRAINING_DATA)
    print(f"✅ 加载 {len(samples)} 条训练样本")

    # 检查 unsloth
    try:
        from unsloth import FastLanguageModel
        print("✅ Unsloth 已安装")
    except ImportError:
        print("❌ Unsloth 未安装，执行: pip install unsloth")
        print("   如果是 Colab，运行:")
        print("   !pip install unsloth")
        return

    import torch

    # 加载模型 (4-bit QLoRA)
    print(f"📥 加载基座模型: {BASE_MODEL}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # auto
        load_in_4bit=True,
    )

    # 添加 LoRA adapter
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=LORA_ALPHA,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # 格式化数据
    texts = [format_alpaca(s) for s in samples]
    print(f"📝 格式化 {len(texts)} 条训练文本")

    # 训练配置
    from transformers import TrainingArguments
    from trl import SFTTrainer

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=texts,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            output_dir=OUTPUT_DIR,
            save_strategy="epoch",
        ),
    )

    print("🚀 开始训练...")
    trainer.train()

    # 保存 LoRA 权重
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"💾 LoRA 权重保存至: {OUTPUT_DIR}")

    # 导出 GGUF (Ollama 可直接加载)
    print("📦 导出 GGUF 量化模型...")
    model.save_pretrained_gguf(
        OUTPUT_DIR,
        tokenizer,
        quantization_method="q4_k_m",
    )
    print(f"🎉 GGUF 模型导出至: {OUTPUT_DIR}")

    # 生成 Ollama Modelfile
    modelfile_content = f"""FROM {OUTPUT_DIR}/unsloth.Q4_K_M.gguf

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM \"\"\"你是 LocalSmartRoute，专精于本地路线规划。擅长意图解析、路线描述生成、POI 氛围匹配、动态调整。\"\"\"
"""
    modelfile_path = os.path.join(OUTPUT_DIR, "Modelfile")
    with open(modelfile_path, "w") as f:
        f.write(modelfile_content)

    print(f"""
╔══════════════════════════════════════════════╗
║         🎉 微调完成！                        ║
╠══════════════════════════════════════════════╣
║  LoRA 权重: {OUTPUT_DIR}          ║
║  Modelfile: {modelfile_path}                ║
╠══════════════════════════════════════════════╣
║  导入 Ollama:                                ║
║  $ ollama create route-planner \\             ║
║      -f {OUTPUT_DIR}/Modelfile   ║
║                                              ║
║  测试:                                       ║
║  $ ollama run route-planner                  ║
╚══════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    run_finetune()
