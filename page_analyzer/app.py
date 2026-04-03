import os

from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import requests
import validators
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

@app.route('/')
def home():
    return render_template('index.html')

@app.post('/urls')
def add_url():
    url_from_form = request.form.get('url', '').strip()

    if not url_from_form:
        flash('URL обязателен', 'danger')
        return render_template('index.html'), 422

    if len(url_from_form) > 255 or not validators.url(url_from_form):
        flash('Некорректный URL', 'danger')
        return render_template('index.html'), 422

    parsed_url = urlparse(url_from_form)
    normalized_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM urls WHERE name = %s", (normalized_url,))
        existing_url = cur.fetchone()

        if existing_url:
            flash('Страница уже существует', 'info')
            conn.close()
            return redirect(url_for('show_url', id=existing_url[0]))

        cur.execute(
            "INSERT INTO urls (name, created_at) VALUES (%s, %s) RETURNING id",
            (normalized_url, datetime.now())
        )
        url_id = cur.fetchone()[0]
        conn.commit()

    conn.close()
    flash('Страница успешно добавлена', 'success')
    return redirect(url_for('show_url', id=url_id))

def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    return psycopg2.connect(database_url)

@app.get('/urls/<int:id>')
def show_url(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, created_at FROM urls WHERE id = %s", (id,))
        url_record = cur.fetchone()

        if not url_record:
            flash('URL не найден', 'danger')
            conn.close()
            return redirect(url_for('get_urls'))

        cur.execute(
            """
            SELECT id, status_code, h1, title, description, created_at
            FROM url_checks
            WHERE url_id = %s
            ORDER BY created_at DESC
            """,
            (id,)
        )
        checks = cur.fetchall()

    conn.close()
    return render_template('urls/show.html', url=url_record, checks=checks)

@app.post('/urls/<int:id>/checks')
def check_url(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM urls WHERE id = %s", (id,))
        url_record = cur.fetchone()

        if not url_record:
            conn.close()
            flash('URL не найден', 'danger')
            return redirect(url_for('get_urls'))

        url_name = url_record[0]

    try:
        response = requests.get(url_name, timeout=10)
        response.raise_for_status()

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO url_checks (url_id, status_code, created_at)
                VALUES (%s, %s, %s)
                """,
                (id, response.status_code, datetime.now())
            )
            conn.commit()

        flash('Страница успешно проверена', 'success')
    except requests.exceptions.RequestException:
        flash('Произошла ошибка при проверке', 'danger')
    finally:
        conn.close()

    return redirect(url_for('show_url', id=id))

@app.get('/urls')
def get_urls():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM urls ORDER BY created_at DESC")
        urls = cur.fetchall()
    conn.close()
    return render_template('urls/index.html', urls=urls)