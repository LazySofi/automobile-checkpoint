import streamlit as st
from bs4 import BeautifulSoup
import requests
import numpy as np
import pandas as pd
import time
from datetime import datetime, timedelta
from math import ceil
import io
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from random import choice



from multiprocessing import Pool, cpu_count
from time import time

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'}

def parse_page(url):
    rows=[]
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    cards = soup.find_all('div', {'class': 'col-12 mb-4'})
    n_cards = int(cards[2].find('div', {'class': 'pin'}).text.split()[-1])

    for card in cards[3:]:
        # пункт пропуска
        name = card.find('h3').text.strip()
        #таможенное управление, таможня
        customs = [t.strip() for t in card.find('p').text.split(',')]

        tmp = card.find('div', {'class': 'col-md-6 mt-2 mt-lg-0'})
        # дата
        date_card = datetime.strptime(tmp.find('h3').text.strip(), '%Y-%m-%d %H:%M')
        # Вид транспортного средства
        vehicle_type = tmp.find('p').text.strip()


        tmp = card.find_all('div', {'class': 'col-12'})[1]
        # Въезд в РФ: Количество АТС перед пунктом пропуска, Количество АТС, оформленных за сутки
        entry = [int(t.text) for t in tmp.find('div', {'class': 'col-md-6'}).find_all('p')]
        # Выезд из РФ: Количество АТС перед пунктом пропуска, Количество АТС, оформленных за сутки
        exit = [int(t.text) for t in tmp.find('div', {'class': 'col-md-6 mt-2 mt-lg-0'}).find_all('p')]

        rows.append([name, customs[0], customs[1], date_card, vehicle_type, entry[0], entry[1], exit[0], exit[1]])
    return rows


def req(date_from="07.07.2023", date_to="07.07.2023", rtu='', cust='', app='', cars='', page=1, rows=[]):
    
    url_f = lambda x: f'https://customs.gov.ru/checkpoints?rtu={rtu}&customs={cust}&app={app}&date_from={date_from}+0%3A10&date_to={date_to}+23%3A59&page={x}&cars={cars}'
    url = url_f(page)
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    cards = soup.find_all('div', {'class': 'col-12 mb-4'})
    n_cards = int(cards[2].find('div', {'class': 'pin'}).text.split()[-1])
    pages = ceil(n_cards/15)

    page_urls = list(map(url_f, list(range(1, pages+1))))
    results = []

    with st.spinner('Загрузка данных'):
        with Pool(min(cpu_count(), len(page_urls))) as p:
            results = p.map(parse_page, page_urls)
    columns = ['Пункт пропуска', 'Таможенное управление', 'Таможня', 'Дата', 'Вид транспортного средства',
           'Въезд в РФ: Количество АТС перед пунктом пропуска', 'Въезд в РФ: Количество АТС, оформленных за сутки',
           'Выезд из РФ: Количество АТС перед пунктом пропуска', 'Выезд из РФ: Количество АТС, оформленных за сутки'
           ]
    return pd.DataFrame([item for pp in results for item in pp], columns=columns)


def download(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.sidebar.download_button(
        label="Скачать Еxcel файл",
        data=buffer,
        file_name="Сведения_о_загруженности_автомобильных_пунктов_пропуска.xlsx",
        mime="application/vnd.ms-excel"
    )


def dashboard(df):
    app_l  = df['Пункт пропуска'].drop_duplicates().to_list()
    cars_l = df['Вид транспортного средства'].drop_duplicates().to_list()

    fig = make_subplots(rows=2, cols=2, subplot_titles=('<span style="font-size: 12px; color: #333366;">Въезд в РФ: Количество АТС перед пунктом пропуска</span>', 
                                                        '<span style="font-size: 12px; color: #333366;">Въезд в РФ: Количество АТС, оформленных за сутки</span>', 
                                                        '<span style="font-size: 12px; color: #333366;">Выезд из РФ: Количество АТС перед пунктом пропуска</span>', 
                                                        '<span style="font-size: 12px; color: #333366;">Выезд из РФ: Количество АТС, оформленных за сутки</span>'))

    colors = ["#"+''.join([choice('0123456789ABCDEF') for j in range(6)]) for i in range(len(app_l)*len(cars_l))]

    for i in range(len(app_l)):
        for j in range(len(cars_l)):
            df_cut = df.loc[(df['Пункт пропуска'] == app_l[i]) & (df['Вид транспортного средства'] == cars_l[j])]
            
            fig.add_trace(go.Scatter(x=df_cut['Дата'], y=df_cut['Въезд в РФ: Количество АТС перед пунктом пропуска'], 
                                     name=f'{app_l[i]} ({cars_l[j]})', line_color=colors[i*len(cars_l)+j], 
                                     legendgroup=f'group{i}-{j}'), 1, 1)
            fig.add_trace(go.Scatter(x=df_cut['Дата'], y=df_cut['Въезд в РФ: Количество АТС, оформленных за сутки'], 
                                     name=f'{app_l[i]} ({cars_l[j]})', line_color=colors[i*len(cars_l)+j], 
                                     legendgroup=f'group{i}-{j}', showlegend=False), 1, 2)
            fig.add_trace(go.Scatter(x=df_cut['Дата'], y=df_cut['Выезд из РФ: Количество АТС перед пунктом пропуска'], 
                                     name=f'{app_l[i]} ({cars_l[j]})', line_color=colors[i*len(cars_l)+j], 
                                     legendgroup=f'group{i}-{j}', showlegend=False), 2, 1)
            fig.add_trace(go.Scatter(x=df_cut['Дата'], y=df_cut['Выезд из РФ: Количество АТС, оформленных за сутки'], 
                                     name=f'{app_l[i]} ({cars_l[j]})', line_color=colors[i*len(cars_l)+j], 
                                     legendgroup=f'group{i}-{j}', showlegend=False), 2, 2)
    
    fig.update_layout(legend_orientation="h",
                  legend=dict(x=.5, xanchor="center"),
                  hovermode="x unified",
                  margin=dict(l=0, r=0, t=30, b=0)
                  )
    fig.update_traces(hoverinfo="all", hovertemplate='<i>кол-во АТС</i>: %{y}')

    st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(page_title = 'Автомобильные пункты пропуска')
    st.title('Сведения о загруженности автомобильных пунктов пропуска')
    st.caption('Данные взяты из Федеральной таможенной службы: https://customs.gov.ru/checkpoints')

    d = st.sidebar.columns(2)
    date_from   = d[0].date_input('Дата с', datetime.now() - timedelta(days=7))
    date_to     = d[1].date_input('Дата дo', datetime.now())

    # Таможенное управление
    rtu = {
        'Все': '',
        'СКТУ': 16,
        'ЮТУ': 13,
        'СТУ': 1,
        'СЗТУ': 8,
        'ЦТУ': 21,
        'ДВТУ': 61,
    }
    rtu_selected = st.sidebar.selectbox('Таможенное управление', rtu, index=6)

    # Таможня
    customs_dict = pd.read_csv('Таможня.csv', index_col=0)
    customs_dict['Код'] = customs_dict['Код'].apply(lambda x: '' if np.isnan(x) else int(x))
    customs_dict = customs_dict.to_dict()['Код']
    customs_selected = st.sidebar.selectbox('Таможня', customs_dict, index=21)

    # Пункт пропуска
    app = pd.read_csv('Пункт пропуска.csv', index_col=0)
    app['Код'] = app['Код'].apply(lambda x: '' if np.isnan(x) else int(x))
    app = app.to_dict()['Код']
    app_selected = st.sidebar.selectbox('Пункт пропуска', app, index=26)

    # Вид транспорта
    cars = {'Все': '', 'Легковые': 1, 'Грузовые': 2}
    cars_selected = st.sidebar.selectbox('Вид транспорта', cars)


    df = pd.DataFrame()
    if st.sidebar.button('Поиск'):
        begin = time()
        df = req(date_from=date_from.strftime('%d.%m.%Y'), date_to=date_to.strftime('%d.%m.%Y'), 
                rtu=rtu[rtu_selected], 
                cust=customs_dict[customs_selected], 
                app=app[app_selected],
                cars=cars[cars_selected])
        download(df)
        st.sidebar.text(f"Время загрузки данных: {round(time() - begin, 2)} с.")

        tab1, tab2 = st.tabs(['Таблица', 'Дашборд'])

        with tab1:
            st.table(df)
        with tab2:
            dashboard(df)


if __name__ == '__main__':
    main()