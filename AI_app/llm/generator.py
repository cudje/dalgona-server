import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pydantic import BaseModel
from typing import Optional
import asyncio


# ── 요청/응답 스키마 ───────────────────────────────────
class PromptRequest(BaseModel):
    userId: str
    stageId: Optional[str] = None
    prompt: str


class ActionResponse(BaseModel):
    code: str                 # 생성된 제어 코드 (문자열)
    promptLen: int            # 프롬프트 길이
    error: Optional[str] = None  # 오류 메시지


model_id = 'Bllossom/llama-3.2-Korean-Bllossom-3B'

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="cuda",
)

SYSTEM_PROMPT = (
    "너는 사용자의 명령을 제어 코드로 바꾸는 AI다.\n"
    "반드시 아래 이동 함수, 부품 조작 함수, 감지 함수만 사용하고 코드만 출력한다. 설명, 따옴표, 주석 금지.\n"
    "현재 아래를 바라보고 있어, 아래가 앞이고 위가 뒤이다."
    "아래는 각 제어코드와 예상 사용자 명령에 대한 내용이다. 예상 사용자 명령이 나오면 이 함수에 해당하는 제어코드로 바꾸어 변환해야 한다.\n"
    "\n"

    "[이동 함수(조건식에 들어갈 수 없음)]\n"
    "- f_move(N): 앞/아래/전방/앞쪽/아랫방향/아래방향/하단 로/으로 N칸/번 이동/움직여/가\n"
    "- b_move(N): 뒤/위/후방/뒤쪽/윗방향/위방향/상단 로/으로 N칸/번 이동/움직여/가\n"
    "- l_move(N): 왼쪽/왼방향/좌방향/좌 로/으로 N칸/번 이동/움직여/가\n"
    "- r_move(N): 오른쪽/오른방향/우방향/우 로/으로 N칸/번 이동/움직여/가\n"
    "\n"

    "[부품 조작 함수(조건식에 들어갈 수 없음)]\n"
    "- pick(): 부품을 줍기/들기\n"
    "- drop(): 부품을 놓기/내리기\n"
    "\n"

    "[감지 함수(반드시 조건식에만 들어갈 수 있음)]\n"
    "- search(1): 앞/아래가 절벽/낭떠러지면\n"
    "- search(2): 뒤/위쪽이 절벽/낭떠러지면\n"
    "- search(3): 왼쪽/좌방향이 절벽/낭떠러지면\n"
    "- search(4): 오른쪽/우방향이 절벽/낭떠러지면\n"
    "→ 반환: 1(있음), 0(없음).\n"
    "\n"

    "[조건식(무조건 절벽/낭떠러지를 검사하는 경우에만 사용함)]\n"
    "형식:\n"
    "if(감지함수){\n"
    "    명령1()\n"
    "    명령2()\n"
    "}\n"
    "else{\n"
    "    명령3()\n"
    "}\n"
    "→ if와 else는 무조건 }로 닫아야 함.\n"
    "\n"

    "[규칙]\n"
    "1. 함수 재정의 금지, 제어 코드만 출력.\n"
    "2. 한 줄에 하나의 제어 코드.\n"
    "3. 비교 연산은 ==, != 만 사용.\n"
    "\n"

    "[예시 1]\n"
    "입력: 아래로 2칸가\n"
    "출력:\n"
    "f_move(2)\n"
    "[예시 2]\n"
    "입력: 위로 1칸가\n"
    "출력:\n"
    "b_move(2)\n"
    "[예시 3]\n"
    "입력: 부품을 주워\n"
    "출력:\n"
    "pick()\n"
    "[예시 4]\n"
    "입력: 아래가 낭떠러지면 뒤로 두칸 가고 그렇지 않으면 오른쪽으로 세번 이동해\n"
    "출력:\n"
    "if(search(1)==1){\n"
    "    b_move(2)\n"
    "}\n"
    "else{\n"
    "    r_move(3)\n"
    "}\n"
    "[예시 종료]\n"
)

async def generate_action(req: PromptRequest) -> ActionResponse:
    try:
        messages = [
            { "role": "system", "content": SYSTEM_PROMPT},
            { "role": "user",   "content": req.prompt}
        ]

        input_ids = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(model.device)

        terminators = [
            tokenizer.convert_tokens_to_ids("<|end_of_text|>"),
            tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        outputs = model.generate(
            input_ids,
            attention_mask=(input_ids != tokenizer.pad_token_id),  # 마스크 지정
            max_new_tokens=768,
            eos_token_id=terminators,
            pad_token_id=tokenizer.pad_token_id,                   # pad_token_id 명시
            do_sample=True,
            temperature=0.1,
            top_p=1.0
        )

        generated = tokenizer.decode(
            outputs[0][input_ids.shape[-1]:],
            skip_special_tokens=True
        ).strip()

        return ActionResponse(
            code=generated,
            promptLen=len(req.prompt)
        )

    except Exception as e:
        return ActionResponse(
            code="",
            promptLen=len(req.prompt),
            error=str(e)
        )
    
if __name__=="__main__":
    promptTest = [
                 ("오른쪽으로 세칸 가", 1),
                 ("오른쪽으로 세칸가", 1),
                 ("오른쪽으로 3칸가", 1),
                 ("오른쪽으로 세칸가고 부품을 주워", 2),
                 ("오른 방향으로 세번 이동하고 바닥에 있는걸 주워", 2),
                 ("우방향으로 세칸간 다음에 줍기를 실행해", 2),
                 ("우로 삼보 이동한 다음에 주워", 2),
                 ("우로 삼보 후 줍기해.", 2),
                 ("왼쪽으로 세칸 가고 주운다음에 뒤로 두칸 가고 내려놓아", 3),
                 ("왼쪽으로 세번 이동하고 줍기를 실행한 다음, 위로 두칸 가고 바닥에 내려놓아", 3),
                 ("왼쪽으로 세칸 이동하고 부품을 주운 다음, 위로 두번 이동하고 부품을 내려놓아", 3),
                 ("아래로 세칸 가고 부품을 주워", 4),
                 ("아래방향으로 세번 이동하고 바닥에 있는 것을 주워", 4),
                 ("앞으로 세번 가고 줍기를 해", 4),
                 ("아래가 절벽이면 위로 두번 이동하고 그게 아니면 오른쪽으로 세번 이동해", 5),
                 ("앞이 낭떠러지면 뒤로 두칸가고 그렇지 않으면 오른쪽으로 세칸 가", 5),
                 ("아래가 낭떠러지면 뒤로 두칸가고 그렇지 않으면 우방향으로 세번 가", 5),
                 ]
    
    ans = {
        1 : "r_move(3)",
        2 : "r_move(3)\npick()",
        3 : "l_move(3)\npick()\nb_move(2)\ndrop()",
        4 : "f_move(3)\npick()",
        5 : "if(search(1)==1){\nb_move(2)\n}\nelse{\nr_move(3)\n}"
    }

    async def main():
        cnt = 0

        for p in promptTest:
            pr = PromptRequest(userId="user", stageId="1", prompt=p[0])
            ac = await generate_action(pr)
            if(p[1] not in ans or ans[p[1]] != ac.code):
                print("=================================")
                print(f"{p[0]} ->")
                print(ac.code)
                print("=================================")
                cnt += 1

        print(f"Accuracy : {(len(promptTest) - cnt) / len(promptTest):.2f}")

    asyncio.run(main())
