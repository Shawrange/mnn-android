from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];d=R/'datasets';d.mkdir(exist_ok=True)
assert not (d/'pilot.jsonl').exists()
cases=[]
def add(category,prompt,gold,rule='exact',variants=None):
    cases.append(dict(id=f'P{len(cases)+1:02}',split='pilot',category=category,input=prompt,gold=gold,variants=variants or ([json.dumps(gold,ensure_ascii=False,separators=(',',':'))] if isinstance(gold,dict) else [gold]),rule=rule,scoring='binary deterministic; strict format; natural EOS required'))
for text,gold in [('请问这家店周末几点开门？','咨询'),('收到的杯子裂了，客服还不处理，我很不满。','投诉'),('包装很用心，配送也快，感谢你们。','表扬')]:add('classification','把下面消息分为咨询、投诉、表扬之一，只输出类别。消息：'+text,gold)
add('extraction','从“联系人是唐宁，预订了4把雨伞”提取信息，只输出JSON，键为name（字符串）、count（整数），不增加其他键。',{'name':'唐宁','count':4},'json_exact')
add('extraction','从“活动在银杏厅举行，开始时间为09:20”提取信息，只输出JSON，键为place、time，值都为字符串。',{'place':'银杏厅','time':'09:20'},'json_exact')
add('extraction','从“周月的快递单号是K825”提取姓名和单号，只输出JSON，键为name、code，值为字符串。',{'name':'周月','code':'K825'},'json_exact')
add('instruction','把数字8、2、5按从小到大排列，只输出一行，用英文逗号分隔。','2,5,8')
add('instruction','将字符串aBc中的英文字母全部变为大写，只输出结果。','ABC')
add('instruction','只输出字符串“完成”，不要引号、标点或其他内容。','完成')
add('qa','短文：旅行包放在卧室的衣柜里。问：旅行包在哪个房间？只输出房间名。','卧室')
add('qa','9减去4等于几？只输出阿拉伯数字。','5')
add('qa','一周有几天？只输出阿拉伯数字。','7')
(d/'pilot.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in cases),encoding='utf-8')
print('Created 12 independent pilot cases')
