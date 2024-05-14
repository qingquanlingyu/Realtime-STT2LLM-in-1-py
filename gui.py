import PySimpleGUI as sg
from multiprocessing import Process,Queue, Pipe
from RealtimeSTT import AudioToTextRecorder
import requests
import json
from openai import OpenAI

model_type = 'deepseek'
ollama_model_name = 'llama3'
client = OpenAI(api_key="", base_url="https://api.deepseek.com")
input_device_ID = 5 #立体声混音，0是默认，可以使用getAudioDevice.py获取

def gui(q, conn):
    url = 'http://localhost:11434/api/generate'
    texts = []
    layout = [[sg.Text('实时语音识别', size=(15,1))],
              [sg.Listbox(texts, size=(50, 12), no_scrollbar=False, expand_y=True, enable_events=True, key='-LIST-')],
              [sg.Button('提交')],
              [sg.Multiline('', auto_refresh=True, autoscroll_only_at_bottom=True, expand_y=True, size=(50,20), key='-ANSWER-')]]
    window = sg.Window('Window Title', layout)
    while True:
        event, values = window.read(timeout=100)
        if event == sg.TIMEOUT_EVENT:
            if not q.empty():
                tmp = q.get()
                if tmp is not None:
                    texts.append(tmp)
                    if (len(texts) > 20):
                        texts = texts[-20:]
                    window['-LIST-'].update(texts)
                    window['-LIST-'].select_index(len(texts)-1)
        elif event == '提交':
            if (model_type == 'ollama'):
                data = {
                    "model": ollama_model_name,
                    "prompt":"用尽可能简洁的中文回复如下问题："+values['-LIST-'][0]
                }
                print(data)
                try:
                    response = requests.post(url, json=data)
                    response.raise_for_status()  # 如果请求不成功，会抛出异常
                    res = ''
                    for i in response.text.split('\n'):
                        if (len(i) > 16):
                            res+=json.loads(i)['response']
                            window['-ANSWER-'].update(res)
                    print(res)
                except requests.exceptions.RequestException as e:
                    window['-ANSWER-'].update("请求出现问题")
                    print(f"请求出现问题: {e}")
                except KeyError:
                    window['-ANSWER-'].update("回复出现问题")
                    print("回复中缺少 'response' 项")   
            elif (model_type == 'deepseek'):
                window['-ANSWER-'].update("等待回答")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是一个精通各种计算机领域知识的助手，你需要用尽可能简洁的中文回答用户的问题，用户的问题是语音识别得到的可能不清晰，此时你需要提取用户提出的内容中有关计算机领域的关键词进行解释"},
                        {"role": "user", "content": "用户的问题："+values['-LIST-'][0]},
                    ],
                    stream=False
                )
                try:
                    window['-ANSWER-'].update(response.choices[0].message.content)
                except KeyError:
                    window['-ANSWER-'].update("接口回复与预期不符，请检查API余额")
                    print("接口回复与预期不符，请检查API")   
        elif event == sg.WINDOW_CLOSED:
            conn.send('close')
            break

if __name__ == '__main__':
    print("启动语音识别模型中...")
    print("可以使用getAudioDevice.py获取输入设备ID，从而更改输入设备")
    with AudioToTextRecorder(model='large-v3', language='zh', input_device_index=input_device_ID) as recorder:
        print("启动完毕，请开始说话...")
        parent_conn, child_conn = Pipe()
        q = Queue()
        p = Process(target=gui, args=(q,child_conn,))
        p.start()
        print("注意，关闭窗口后需要说句话才能关闭语音识别进程！")
        def process_text(text):
            q.put(text)   
            print('')
        while True:
            if parent_conn.poll():
                message = parent_conn.recv()
                if message == 'close':
                    p.terminate()
                    break
            recorder.text(process_text)
        p.join()