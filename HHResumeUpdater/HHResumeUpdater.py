#
# Python
# HHResumeUpdater
# v1.2, 19.07.2024
# https://github.com/dkxce/HHResumeUpdater
# en,ru,1251,utf-8
#
# HOW TO:     https://habr.com/ru/companies/hh/articles/303168/
# HH API 1.0: https://dev.hh.ru/ https://api.hh.ru/openapi/redoc
# CallBack:   http://localhost:8008/?code=XXXXXX&state=000000
#

import os
import re
import sys
import socket
import hashlib
import argparse
import requests
import webbrowser 
import urllib.parse

from pathlib import Path


USE_PYWEBIO    = True # Web Interface 4 Select Resume IDs for Update # https://pywebio.readthedocs.io/en/latest/
USER_AGENT     = 'dkxce-HH-syntaxer/1.2 (dkxce@mail.ru)' # Application Name
CLIENT_ID      = '_' # KEEP IN SECRET
CLIENT_SECRET  = '_' # KEEP IN SECRET

OAUTH_URL      = 'https://hh.ru/oauth/authorize?response_type=code&client_id={client_id}&state={state}&redirect_uri={redirect_uri}'
REDIRECT_HOST  = '127.0.0.1'
REDIRECT_PORT  = 8008

BEARER_TOKEN   = os.environ.get('BEARER_TOKEN', '').strip()
TOKEN_FILE     = './HHResumeUpdater.token'
RESUME_IDS_2UP = [resume_id.strip() for resume_id in os.environ.get('RESUME_IDS_2UP', '').split(',') if resume_id]

PUBLISH_LOCALE = "RU"
PUBLISH_HOST   = "hh.ru"


def __is_port_in_use__(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def __get_free_port_from__(port: int) -> int:
    while __is_port_in_use__(port): port += 1
    return port


def __get_authorization_code__(state: str, port: int) -> str:
    '''
    https://oauth.net/2/
    '''
    
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((REDIRECT_HOST, port))
    sock.listen(1)
    connection, _ = sock.accept()
    
    data = connection.recv(2048)    
    params = __parse_raw_query_params__(data)
    
    try:
        if not params.get("code"):
            error = params.get("error")
            message = f"<b>Не удается получить код авторизации. Ошибка: {error}</b>"
            raise ValueError(message)
        elif params.get("state") != state:
            message = "<b>Параметр state не соответствует преденной информации.</b>"
            raise ValueError(message)
        else:
            code = params.get("code")
            message = f"<b>Код авторизации успешно получен.</b><br/>"
            message += (f"Ваш код авторизации: `<b>{code}</b>`")
    except ValueError as error:
        print(error)
        if __name__ == "__main__": sys.exit(1)
        raise error
    finally:
        response = (f"HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\n\n{message}")
        connection.sendall(response.encode())
        connection.close()
    return params.get("code")


def __parse_raw_query_params__(data) -> dict:
    decoded = data.decode("utf-8")
    match = re.search(r"GET\s\/\?(.*) ", decoded)
    params = match.group(1)
    pairs = [pair.split("=") for pair in params.split("&")]
    return {key: val for key, val in pairs}


def __hprint__(line: str) -> None:
    print(line)
    if USE_PYWEBIO:
        try:
            from pywebio import output
            output.put_text(line)
        except: pass
        
        
def __web_select_resume_ids__(resume_list: dict) -> list:
    from pywebio import input, output
    keyword = input.checkbox('Выберите резюме для обновления публикации', options = resume_list, value = [k for k,_ in resume_list.items()])
    output.clear()
    return keyword
    

def hh_get_auth_token() -> str:
    '''
    https://api.hh.ru/openapi/redoc#section/Avtorizaciya/Avtorizaciya-polzovatelya
    '''
    
    port = __get_free_port_from__(REDIRECT_PORT) if REDIRECT_HOST in ['127.0.0.1','localhost'] else REDIRECT_PORT
    
    state = hashlib.sha256(os.urandom(1024)).hexdigest()
    redirect_uri = urllib.parse.quote( f'http://{REDIRECT_HOST}:{port}/', safe = '')  
    
    url = OAUTH_URL.replace('{client_id}', CLIENT_ID).replace('{state}', state).replace('{redirect_uri}', redirect_uri)    
    webbrowser.open(url)
    print(f'Откройте ссылку в браузере:\n\n{url}\n')
    
    code = urllib.parse.unquote(__get_authorization_code__(state, port))
    
    print(f"Код авторизации успешно получен.")
    print(f"Ваш код авторизации: `{code}`")
    
    return code


def hh_get_bearer_token(auth_token: str) -> str:
    '''
    https://api.hh.ru/openapi/redoc#tag/Avtorizaciya-soiskatelya
    '''
    
    url = 'https://api.hh.ru/token'
    headers = {'User-Agent': USER_AGENT, 'Content-Type': 'application/x-www-form-urlencoded'}
    redirect_uri = urllib.parse.quote( f'http://{REDIRECT_HOST}:{REDIRECT_PORT}/', safe = '')  
    body = f'grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={auth_token}&redirect_uri={redirect_uri}'
    
    resp = requests.post(url,body,headers=headers)
    respj = resp.json()
    
    if error := respj.get('error') or respj.get('errors'): raise Exception(error)
    bearer_token = respj.get('access_token')
    
    print(f"Bearer token успешно получен.")
    print(f"Bearer token ключ: `{bearer_token}`")  
    
    return bearer_token


def hh_get_resume_list(bearer_token: str) -> dict:
    '''
    https://api.hh.ru/openapi/redoc#tag/Rezyume.-Prosmotr-informacii/operation/get-mine-resumes
    '''
    
    url = 'https://api.hh.ru/resumes/mine'
    headers = {'User-Agent': USER_AGENT, 'Authorization': f'Bearer {bearer_token}'}
    
    resp = requests.get(url,headers=headers)
    respj = resp.json()
    
    if error := respj.get('error') or respj.get('errors'): raise Exception(error)
    
    return respj
    

def hh_update_resume_date(bearer_token: str, resume_id: str) -> bool:
    '''
    https://api.hh.ru/openapi/redoc#tag/Rezyume.-Publikaciya
    '''
    
    url = f'https://api.hh.ru/resumes/{resume_id}/publish?locale={PUBLISH_LOCALE}&host={PUBLISH_HOST}'
    headers = {'User-Agent': USER_AGENT, 'Authorization': f'Bearer {bearer_token}'}
    
    resp = requests.post(url,headers=headers)
    respj = resp.json()
    
    if error := respj.get('error') or respj.get('errors'): raise Exception(error)
    
    return resp.status_code == 204


def find_resume_by_id(mine: dict, resume_id: str) -> dict:
    for item in mine['items']:
        if item["id"] == resume_id: return item
    return {}


if __name__ == "__main__":

    print(USER_AGENT)    

    # Get Cmd Line Args
    parser = argparse.ArgumentParser()
    parser.add_argument("-t","--token",type=str,required=False,help="Ключ Bearer Token",)
    parser.add_argument("-r","--resume",type=str,required=False,help="Список ID резюме через запятую",)
    parser.print_help(sys.stderr)
    args = parser.parse_args()
    
    print('\n... подожддите, идет загрузка ...\n')
    
    # Check Resume IDs Update List
    if args.resume not in [None,'','.']:        
        resume_ids = [resume_id.strip() for resume_id in args.resume.split(',') if resume_id]
        print(f'\nСписок резюме (из командной строки): {resume_ids}')
    else:
        resume_ids = RESUME_IDS_2UP
        print(f'\nСписок резюме (из переменной окружения): {resume_ids}')
    if not resume_ids:
        print('\nСписок резюме для обновления пуст !!!\n  Используйте следующий синтаксис для запуска приложения:\n  > HHResumeUpdater -r *\n     или\n  > HHResumeUpdater -r my_resume_id\n') 
    my_resume_list = {'items':[]}
    
    pass # debug breakpoint
    
    # Check/Get Bearer Token
    if args.token not in [None,'','.']:
        bearer_token = args.token
        print(f'\nBearer token (из командной строки): {bearer_token}')
    elif BEARER_TOKEN:
        bearer_token = BEARER_TOKEN
        print(f'\nBearer token (из переменной окружения): {bearer_token}')
    elif (tfile := Path(TOKEN_FILE)) and tfile.is_file():
        with open(TOKEN_FILE) as file: bearer_token = file.readline()
        print(f'\nBearer token (из файла): {bearer_token}')
    else:
        print('\nАвторизация... ')
        auth_token = hh_get_auth_token()
        print('\Получение Bearer Token ... ')
        try: 
            bearer_token = hh_get_bearer_token(auth_token)
            with open(TOKEN_FILE, 'w') as file: file.write(bearer_token)
            print(f'\nBearer token сохранен в файл {TOKEN_FILE}')
        except Exception as ex:
            print(f'Ошибка получеыния Bearer Token: {ex}')
            sys.exit(1)
        
    pass # debug breakpoint
        
    # Get My Resume IDs
    print('\nПолучение списка моих резюме ... ')
    try: my_resume_list = hh_get_resume_list(bearer_token)
    except Exception as ex:
        print(f'Ошибка получения списка моих резюме: {ex}')
        print(f'Примечание: если срок действия bearer token истек - удалите файл {TOKEN_FILE}')
        sys.exit(1)
        
    pass # debug breakpoint
        
    # Print My Resume IDs
    print('\n---- МОИ РЕЗЮМЕ ----\n')
    for item in my_resume_list['items']:
        print(f'- {item["title"]} - {item["id"]}, {item["updated"]}')
        
    pass # debug breakpoint
    
    # Check If Update All
    if resume_ids and len(resume_ids) == 1 and resume_ids[0] == '*':
        resume_ids = [item["id"] for item in my_resume_list['items']]
        
    pass # debug breakpoint
        
    # If Update List not set then Select From List
    if not resume_ids and (items := my_resume_list["items"]) and USE_PYWEBIO:
        if len(items) == 1: 
            resume_ids =[items[0]['id']]
        else:
            rdict = {f'{item["title"]}': item["id"] for item in items if item["title"]}
            ids = __web_select_resume_ids__(rdict)
            resume_ids = [rdict[title] for title in ids]
            __hprint__(f"Выбранные резюме для обновления публикации: {', '.join(resume_ids)}") 
        
    pass # debug breakpoint

    # Update
    if not resume_ids:
        
        __hprint__('\n---- НЕТ РЕЗЮМЕ ДЛЯ ОБНОВЛЕНИЯ ПУБЛИКАЦИИ ----\n')  
        
    else:
        
        __hprint__('\n---- ОБНОВЛЕНИЯ ПУБЛИКАЦИИ РЕЗЮМЕ ----\n')    
        for resume_id in resume_ids:
            # resume_id += '0' #
            err = ''
            try: ok = hh_update_resume_date(bearer_token, resume_id)
            except Exception as ex:
                ok = False
                err = ex
            updated_text = 'успешно обновлено' if ok else f'ошибка ({err})'
            resume_text = f'{find_resume_by_id(my_resume_list, resume_id).get("title")} - {resume_id}'
            __hprint__(f'- {resume_text} - {updated_text}')
           
    pass # debug breakpoint

    __hprint__('\n---- ГОТОВО ----\n')