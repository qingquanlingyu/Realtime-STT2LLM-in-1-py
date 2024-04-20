import PySimpleGUI as sg
from multiprocessing import Process,Queue, Pipe
from RealtimeSTT import AudioToTextRecorder
import requests
import json

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
            data = {
                "model": "llama3",
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
            
        elif event == sg.WINDOW_CLOSED:
            conn.send('close')
            break

if __name__ == '__main__':
    print("启动语音识别模型中...")
    with AudioToTextRecorder(model='large-v3', language='zh') as recorder:
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
    