#!/usr/bin/env python3
"""チャットに出す日本語の確かめ方を、追加の文脈として渡す（ユーザーの指定、2026-10-28）。発言を受け取るとき（UserPromptSubmit）と、
ツールを使い終えるたび（PostToolUse。次の一言を書く前）に呼ぶ。引数はイベントの名前。
語の一覧は持たない（個別の禁止語と代わりの語を並べても、きりがないため。ユーザーの指定）。"""
import json
import re
import sys

LANG = ("- まず、すべて日本語か。ツールの前後の一言・報告の見出しも含めて、英語の文が 1 つもないか"
        "（英語の指示・ツールの結果・会話の要約を読んだ直後に崩れやすい。2026-10-29 に要約の直後の報告がまるごと英語になった）。\n")

text = ("【チャットに出す前の確認（ユーザーの指定）】返答・途中の一言・報告のすべてで、出す前に一文ずつ確かめる：\n"
        + LANG +
        "- 英語で考えた語を和語に置き換えただけの言い方（直訳語）や、作業の中でしか通じない口語的な言い方になっていないか。"
        "一般の日本語の文書・公式の文書で使われる、硬くて正確な用語で書く（CLAUDE.md の作業のルール 2）。\n"
        "- 動詞の連用形で言い切り、それだけで名詞として使っていないか（例：「試し」「途切れ」は不可。格を破った言い方で、口語的・機械翻訳的に感じられる）。"
        "連用形のあとに名詞が付く複合語（試し方・つなぎ目・引き込み線）と、一般に名詞として定着した語（行き止まり）はよい。定着しているかは 1 語ずつ判断する。"
        "連用形の名詞を、固まった概念を表す用語にしない（内容に合う語を選ぶ。例：勾配なら変化点）。"
        "正式な行為の記述に、俗語的な動詞を使わない（例：「埋める」ではなく「補う」）。"
        "使いそうになったことに気づいたら、その返答の中で自己申告する（ユーザーの指定。hook が働いているかを確かめるため、当面）。\n"
        "- 前提知識のない読み手が、同じ意味に取れるか。何と何か・何の数か・だから何かが書かれているか（CLAUDE.md の作業のルール 3）。")
event = sys.argv[1] if len(sys.argv) > 1 else "UserPromptSubmit"
EN = lambda t: (lambda t: len(re.findall(r"[A-Za-z]", t)) > 15 and len(re.findall(r"[A-Za-z]", t)) > 3 * len(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", t)))(
    re.sub(r"`[^`]*`|https?://\S+|[\w./-]+\.(py|js|json|html|md)", "", t))
if event == "Stop":
    # the final reply in English (2026-11-06: a whole report came out in English): stop and have it rewritten once
    try: d = json.load(sys.stdin)
    except Exception: d = {}
    if not d.get("stop_hook_active") and EN(d.get("last_assistant_message", "")):
        json.dump({"decision": "block", "reason": "最後の返答が英語だった。同じ内容を日本語で書き直して返答する（ユーザーへの出力はすべて日本語）。"}, sys.stdout, ensure_ascii=False)
    sys.exit(0)


def last_text():
    """the assistant's latest text in the transcript (2026-11-06: an English remark becomes the model for the next ones, so point it out at once)"""
    try:
        f = open(json.load(sys.stdin)["transcript_path"], "rb"); f.seek(0, 2); f.seek(max(0, f.tell() - 300000))
        for line in reversed(f.read().decode("utf-8", "ignore").splitlines()):
            e = json.loads(line) if line.startswith("{") else {}
            if e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), str): return ""
            if e.get("type") == "assistant":
                t = "".join(b.get("text", "") for b in e["message"].get("content", []) if b.get("type") == "text")
                if t.strip(): return t
    except Exception:
        pass
    return ""


if event == "PostToolUse":
    t = last_text()
    if EN(t):
        seen = "/tmp/wording_reminder_seen"   # the transcript is written late: do not point out the same remark twice
        try: done = open(seen, encoding="utf-8").read()
        except OSError: done = ""
        if t.strip()[:80] not in done:
            open(seen, "a", encoding="utf-8").write(t.strip()[:80] + "\n")
            text = f"【直前の一言が英語だった：「{t.strip()[:80]}」。次の一言から日本語で書く（英語の一言は、次の一言の手本になって増える）】\n" + text
if event == "SessionStart":
    # 会話の要約のあと（compact）と再開のとき。要約は英語で書かれるので、最初の出力から日本語にする
    text = ("【会話の要約のあとの注意（ユーザーの指定）】上の要約は英語で書かれているが、ユーザーへの出力はすべて日本語で書く"
            "（最初の一言から。CLAUDE.md の作業のルール 1）。"
            "途中の一言の例：「計算が終わりました。結果を確かめます。」「テストがすべて通りました。PR を作ります。」「想定と違う値が出ました。原因を調べます。」\n" + text)
json.dump({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, sys.stdout, ensure_ascii=False)
