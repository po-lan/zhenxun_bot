import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime
from .config import DRAW_PATH
from pathlib import Path
from asyncio.exceptions import TimeoutError
from services.log import logger
try:
    import ujson as json
except ModuleNotFoundError:
    import json

headers = {'User-Agent': '"Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; TencentTraveler 4.0)"'}

prts_up_char = Path(DRAW_PATH + "/draw_card_up/prts_up_char.json")
genshin_up_char = Path(DRAW_PATH + "/draw_card_up/genshin_up_char.json")
pretty_up_char = Path(DRAW_PATH + "/draw_card_up/pretty_up_char.json")

prts_url = "https://wiki.biligame.com/arknights/%E6%96%B0%E9%97%BB%E5%85%AC%E5%91%8A"
genshin_url = "https://wiki.biligame.com/ys/%E7%A5%88%E6%84%BF"
pretty_url = "https://wiki.biligame.com/umamusume/%E5%85%AC%E5%91%8A"


# 是否过时
def is_expired(data: dict):
    times = data['time'].split('-')
    for i in range(len(times)):
        times[i] = str(datetime.now().year) + '-' + times[i].split('日')[0].strip().replace('月', '-')
    start_date = datetime.strptime(times[0], '%Y-%m-%d').date()
    end_date = datetime.strptime(times[1], '%Y-%m-%d').date()
    now = datetime.now().date()
    return start_date <= now <= end_date


# 检查写入
def check_write(data: dict, up_char_file, game_name: str = ''):
    tmp = data
    if game_name == 'genshin':
        tmp = data['char']
    if not is_expired(tmp):
        if game_name == 'genshin':
            data['char']['title'] = ''
            data['arms']['title'] = ''
        else:
            data['title'] = ''
    else:
        with open(up_char_file, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    if not up_char_file.exists():
        with open(up_char_file, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    else:
        with open(up_char_file, 'r', encoding='utf8') as f:
            old_data = json.load(f)
            tmp = old_data
            if game_name == 'genshin':
                tmp = old_data['char']
        if is_expired(tmp):
            return old_data
        else:
            with open(up_char_file, 'w', encoding='utf8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    return data


def _get_up_char(r: str, text: str):
    pr = re.search(r, text)
    chars = pr.group(1)
    probability = pr.group(2)
    chars = chars.replace('[限定]', '').replace('[', '').replace(']', '')
    probability = probability.replace('【', '')
    return chars, probability


class PrtsAnnouncement:

    @staticmethod
    async def get_announcement_text():
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(prts_url, timeout=7) as res:
                soup = BeautifulSoup(await res.text(), 'lxml')
                trs = soup.find('table').find('tbody').find_all('tr')
                for tr in trs:
                    a = tr.find_all('td')[-1].find('a')
                    if a.text.find('寻访') != -1:
                        url = a.get('href')
                        break
            async with session.get(f'https://wiki.biligame.com/{url}', timeout=7) as res:
                return await res.text(), a.text[:-4]

    @staticmethod
    async def update_up_char():
        prts_up_char.parent.mkdir(parents=True, exist_ok=True)
        data = {'up_char': {'6': {}, '5': {}, '4': {}}, 'title': '', 'time': '', 'pool_img': ''}
        try:
            text, title = await PrtsAnnouncement.get_announcement_text()
            soup = BeautifulSoup(text, 'lxml')
            data['title'] = title
            context = soup.find('div', {'id': 'mw-content-text'}).find('div')
            data['pool_img'] = str(context.find('div', {'class': 'center'}).find('div').find('a').
                                   find('img').get('srcset')).split(' ')[-2]
            # print(context.find_all('p'))
            for p in context.find_all('p')[1:]:
                if p.text.find('活动时间') != -1:
                    pr = re.search(r'.*?活动时间：(.*)', p.text)
                    data['time'] = pr.group(1)
                elif p.text.find('★★★★★★') != -1:
                    chars, probability = _get_up_char(r'.*?★★★★★★：(.*?)（.*?出率的?(.*?)%.*?）.*?', p.text)
                    slt = '/'
                    if chars.find('\\') != -1:
                        slt = '\\'
                    for char in chars.split(slt):
                        data['up_char']['6'][char.strip()] = probability.strip()
                elif p.text.find('★★★★★') != -1:
                    chars, probability = _get_up_char(r'.*?★★★★★：(.*?)（.*?出率的?(.*?)%.*?）.*?', p.text)
                    slt = '/'
                    if chars.find('\\') != -1:
                        slt = '\\'
                    for char in chars.split(slt):
                        data['up_char']['5'][char.strip()] = probability.strip()
                elif p.text.find('★★★★') != -1:
                    chars, probability = _get_up_char(r'.*?★★★★：(.*?)（.*?出率的?(.*?)%.*?）.*?', p.text)
                    slt = '/'
                    if chars.find('\\') != -1:
                        slt = '\\'
                    for char in chars.split(slt):
                        data['up_char']['4'][char.strip()] = probability.strip()
                    break
                pr = re.search(r'.*?★：(.*?)（在(.*?)★.*?以(.*?)倍权值.*?）.*?', p.text)
                if pr:
                    char = pr.group(1)
                    star = pr.group(2)
                    weight = pr.group(3)
                    char = char.replace('[限定]', '').replace('[', '').replace(']', '')
                    data['up_char'][star][char.strip()] = f'权{weight}'
            # data['time'] = '03月09日16:00 - 05月23日03:5
        except TimeoutError:
            print(f'更新明日方舟UP池信息超时...')
            with open(prts_up_char, 'r', encoding='utf8') as f:
                data = json.load(f)
        return check_write(data, prts_up_char)


class GenshinAnnouncement:

    @staticmethod
    async def get_announcement_text():
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(genshin_url, timeout=7) as res:
                return await res.text()

    @staticmethod
    async def update_up_char():
        genshin_up_char.parent.mkdir(exist_ok=True, parents=True)
        data = {
            'char': {'up_char': {'5': {}, '4': {}}, 'title': '', 'time': '', 'pool_img': ''},
            'arms': {'up_char': {'5': {}, '4': {}}, 'title': '', 'time': '', 'pool_img': ''}
        }
        text = await GenshinAnnouncement.get_announcement_text()
        soup = BeautifulSoup(text, 'lxml')
        try:
            div = soup.find_all('div', {'class': 'row'})[1]
            tables = div.find_all('table', {'class': 'wikitable'})
            for table in tables:
                trs = table.find('tbody').find_all('tr')
                pool_img = trs[0].find('th').find('img')
                if pool_img['title'].find('角色活动') == -1:
                    itype = 'arms'
                else:
                    itype = 'char'
                try:
                    data[itype]['pool_img'] = str(pool_img['srcset']).split(' ')[0]
                except KeyError:
                    data[itype]['pool_img'] = pool_img['src']
                data[itype]['title'] = str(pool_img['title']).split(f'期{"角色" if itype == "char" else "武器"}')[0][:-3]
                data[itype]['time'] = trs[1].find('td').text
                if data[itype]['time'][-1] == '\n':
                    data[itype]['time'] = data[itype]['time'][:-1]
                tmp = ''
                for tm in data[itype]['time'].split('~'):
                    date_time_sp = tm.split('/')
                    date_time_sp[2] = date_time_sp[2].strip().replace(' ', '日 ')
                    tmp += date_time_sp[1] + '月' + date_time_sp[2] + ' - '
                data[itype]['time'] = tmp[:-2].strip()
                for a in trs[2].find('td').find_all('a'):
                    char_name = a['title']
                    data[itype]['up_char']['5'][char_name] = "50"
                for a in trs[3].find('td').find_all('a'):
                    char_name = a['title']
                    data[itype]['up_char']['4'][char_name] = "50"
        except TimeoutError as e:
            logger.warning(f'更新原神UP池信息超时...')
            with open(genshin_up_char, 'r', encoding='utf8') as f:
                data = json.load(f)
        except Exception as e:
            print(f'更新原神UP失败，疑似UP池已结束， e：{e}')
            with open(genshin_up_char, 'r', encoding='utf8') as f:
                data = json.load(f)
                data['char']['title'] = ''
                data['arms']['title'] = ''
            with open(genshin_up_char, 'w', encoding='utf8') as wf:
                json.dump(data, wf, ensure_ascii=False, indent=4)
            return data
        return check_write(data, genshin_up_char, 'genshin')


class PrettyAnnouncement:
    @staticmethod
    async def get_announcement_text():
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(pretty_url, timeout=7) as res:
                soup = BeautifulSoup(await res.text(), 'lxml')
                divs = soup.find('div', {'id': 'mw-content-text'}).find('div').find_all('div')
                for div in divs:
                    a = div.find('a')
                    try:
                        title = a['title']
                    except (KeyError, TypeError):
                        continue
                    if title.find('新角色追加') != -1:
                        url = a['href']
                        break
            async with session.get(f'https://wiki.biligame.com/{url}', timeout=7) as res:
                return await res.text(), title[:-2]

    @staticmethod
    async def update_up_char():
        data = {
            'char': {'up_char': {'3': {}, '2': {}, '1': {}}, 'title': '', 'time': '', 'pool_img': ''},
            'card': {'up_char': {'3': {}, '2': {}, '1': {}}, 'title': '', 'time': '', 'pool_img': ''}
        }
        try:
            text, title = await PrettyAnnouncement.get_announcement_text()
            soup = BeautifulSoup(text, 'lxml')
            context = soup.find('div', {'class': 'toc-sticky'})
            if not context:
                context = soup.find('div', {'class': 'mw-parser-output'})
            data['char']['title'] = title
            data['card']['title'] = title
            time = str(context.find_all('big')[1].text)
            time = time.replace('～', '-').replace('/', '月').split(' ')
            time = time[0] + '日 ' + time[1] + ' - ' + time[3] + '日 ' + time[4]
            data['char']['time'] = time
            data['card']['time'] = time
            for p in context.find_all('p'):
                if str(p).find('当期UP赛马娘') != -1:
                    data['char']['pool_img'] = p.find('img')['src']
                    r = re.findall(r'.*?当期UP赛马娘([\s\S]*)＜奖励内容＞.*?', str(p))
                    if r:
                        for x in r:
                            x = str(x).split('\n')
                            for msg in x:
                                if msg.find('★') != -1:
                                    msg = msg.replace('<br/>', '')
                                    msg = msg.split(' ')
                                    if (star := len(msg[0].strip())) == 3:
                                        data['char']['up_char']['3'][msg[1]] = '70'
                                    elif star == 2:
                                        data['char']['up_char']['2'][msg[1]] = '70'
                                    elif star == 1:
                                        data['char']['up_char']['1'][msg[1]] = '70'
                if str(p).find('（当期UP对象）') != -1 and str(p).find('赛马娘') == -1:
                    data['card']['pool_img'] = p.find('img')['src']
                    r = re.search(r'■全?新?支援卡（当期UP对象）([\s\S]*)</p>', str(p))
                    if r:
                        rmsg = r.group(1)
                        rmsg = rmsg.split('<br/>')
                        for x in rmsg[1:]:
                            x = x.replace('\n', '').replace('・', '')
                            x = x.split(' ')
                            if x[0] == 'SSR':
                                data['card']['up_char']['3'][x[1]] = '70'
                            if x[0] == 'SR':
                                data['card']['up_char']['2'][x[1]] = '70'
                            if x[0] == 'R':
                                data['card']['up_char']['1'][x[1]] = '70'
            # 日文->中文
            with open(DRAW_PATH + 'pretty_card.json', 'r', encoding='utf8') as f:
                all_data = json.load(f)
            for star in data['card']['up_char'].keys():
                for name in list(data['card']['up_char'][star].keys()):
                    char_name = name.split(']')[1].strip()
                    tp_name = name[name.find('['): name.find(']') + 1].strip().replace('[', '【').replace(']', '】')
                    for x in all_data.keys():
                        if all_data[x]['名称'].find(tp_name) != -1 and all_data[x]['关联角色'] == char_name:
                            data['card']['up_char'][star].pop(name)
                            data['card']['up_char'][star][all_data[x]['中文名']] = '70'
        except TimeoutError:
            logger.warning(f'更新赛马娘UP池信息超时...')
            with open(pretty_up_char, 'r', encoding='utf8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f'赛马娘up更新失败 {type(e)}：{e}')
        return check_write(data, pretty_up_char, 'pretty')
