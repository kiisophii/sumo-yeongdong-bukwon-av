"""수집한 주행 데이터셋을 HuggingFace Hub에 업로드 (평가 항목: "HuggingFace에 데이터 업로드").

※ 업로드는 본인 계정으로 직접 로그인한 뒤 실행하세요. 토큰을 코드에 적지 마세요.
    pip install huggingface_hub
    huggingface-cli login          # 브라우저에서 발급한 Write 토큰을 입력 (본인이 직접)
    python tools/upload_hf.py --repo <HF아이디>/sumo-yeongdong-bukwon-av --data-dir data/release

data-dir 안의 *.npz / *.jsonl.gz 와 README.md(데이터셋 카드)를 그대로 올린다.
README.md가 없으면 docs/hf_dataset_card.md를 복사해서 사용한다.
"""
import argparse
import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="예: myname/sumo-yeongdong-bukwon-av")
    ap.add_argument("--data-dir", default=os.path.join(BASE, "data", "release"))
    ap.add_argument("--private", action="store_true", help="비공개 저장소로 생성")
    args = ap.parse_args()

    from huggingface_hub import HfApi

    card = os.path.join(args.data_dir, "README.md")
    if not os.path.exists(card):
        shutil.copy(os.path.join(BASE, "docs", "hf_dataset_card.md"), card)

    api = HfApi()
    api.create_repo(args.repo, repo_type="dataset", private=args.private, exist_ok=True)
    api.upload_folder(folder_path=args.data_dir, repo_id=args.repo, repo_type="dataset",
                      allow_patterns=["*.npz", "*.jsonl.gz", "*.md", "*.json"])
    print(f"업로드 완료: https://huggingface.co/datasets/{args.repo}")


if __name__ == "__main__":
    main()
