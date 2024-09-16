from flask import Flask
import os
from functools import wraps
from datetime import datetime
from flask import Flask, request, redirect, session, render_template, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from datetime import datetime


app = Flask(__name__)

# Imposta la chiave segreta utilizzando una variabile d'ambiente
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Verifica se la chiave segreta è impostata, se no, stampa un avviso
if app.secret_key is None:
    print("Attenzione: FLASK_SECRET_KEY non è impostata!")

# Funzione per ottenere la connessione al database
def get_db_connection():

    print(f'Host:', os.getenv('MYSQL_HOST'))
    print(f'User:', os.getenv('MYSQL_USER'))
    print(f'Password:', os.getenv('MYSQL_PASSWORD'))
    print(f'Database:', os.getenv('MYSQL_DB'))
    print(f'Port:', os.getenv('MYSQL_PORT'))

    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DB')
    )

# Decoratore per verificare se l'utente è admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user or not user['is_admin']:
            return redirect('/home')
        return f(*args, **kwargs)
    return decorated_function

# Pagina di login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Modifica qui: usa 'username' invece di 'email'
        username = request.form['username']
        password = request.form['password']

        # Connessione al database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Modifica qui: seleziona l'utente in base allo username
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        # Chiusura della connessione
        cursor.close()
        conn.close()

        # Verifica la password e gestisce il login
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect('/home')
        else:
            return 'Credenziali non valide', 401

    # Se GET, visualizza il form di login
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form['nome']
        cognome = request.form['cognome']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Verifica che le password corrispondano
        if password != confirm_password:
            flash('Le password non corrispondono. Riprova.', 'error')
            return redirect('/register')

        hashed_password = generate_password_hash(password, method='sha256')

        # Controlla se l'username o l'email sono già registrati
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
        existing_user = cursor.fetchone()
        if existing_user:
            flash('Username o email già registrati. Riprova con un\'altra.', 'error')
            cursor.close()
            conn.close()
            return redirect('/register')

        try:
            # Inserisce il nuovo utente nel database
            cursor.execute('INSERT INTO users (nome, cognome, username, email, password) VALUES (%s, %s, %s, %s, %s)',
                           (nome, cognome, username, email, hashed_password))
            conn.commit()
            flash('Registrazione avvenuta con successo. Puoi ora effettuare il login.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Errore durante la registrazione: {e}', 'error')
        finally:
            cursor.close()
            conn.close()

        return redirect('/')

    return render_template('register.html')


# Pagina home
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        now = datetime.now()
        if 'mark_in' in request.form:
            print(f'Provando ad entrare! (:',user_id,')')
            # Verifica se c'è già un'entrata in corso
            cursor.execute('SELECT * FROM presenze WHERE user_id = %s AND ora_uscita IS NULL',
                                        (session['user_id'],))
            current_entry = cursor.fetchone()
            if current_entry:
                flash('Hai già registrato un\'entrata in corso. Devi segnare l\'uscita prima di segnare una nuova entrata.', 'error')
            else:
                cursor.execute('INSERT INTO presenze (user_id, ora_entrata) VALUES (%s, %s)',
                             (session['user_id'], now))
                conn.commit()
                flash('Entrata registrata con successo.', 'success')
        elif 'mark_out' in request.form:
            print(f'Provando ad uscire! (:',user_id,')')
            # Verifica se c'è un'entrata registrata
            cursor.execute('SELECT * FROM presenze WHERE user_id = %s AND ora_uscita IS NULL',
                                        (session['user_id'],))
            current_entry = cursor.fetchone()
            if not current_entry:
                flash('Non hai registrato alcuna entrata. Non puoi segnare l\'uscita.', 'error')
            else:
                cursor.execute('UPDATE presenze SET ora_uscita = %s WHERE id = %s',
                             (now, current_entry['id']))
                conn.commit()
                flash('Uscita registrata con successo.', 'success')

    # Recupera le informazioni dell'utente
    cursor.execute('SELECT nome, cognome, is_admin, coffee_count FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('home.html', user=user)

from flask import Flask, request, jsonify, session, render_template, redirect
import mysql.connector

# Rotta per visualizzare la pagina delle richieste di amicizia
@app.route('/friend_requests')
def friend_requests():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Recupera le richieste di amicizia ricevute
    cursor.execute('''
        SELECT r.id, u.nome, u.cognome, u.username, u.coffee_count 
        FROM friend_requests r
        JOIN users u ON r.sender_id = u.id
        WHERE r.receiver_id = %s AND r.status = 'pending'
    ''', (user_id,))
    received_requests = cursor.fetchall()

    # Recupera la lista degli amici e ordina per numero di caffè decrescente
    cursor.execute('''
        SELECT u.id, u.nome, u.cognome, u.username, u.coffee_count
        FROM friends f
        JOIN users u ON (f.user_id_1 = u.id OR f.user_id_2 = u.id)
        WHERE (f.user_id_1 = %s OR f.user_id_2 = %s) AND u.id != %s
        ORDER BY u.coffee_count DESC
    ''', (user_id, user_id, user_id))
    friends = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('friend_requests.html', 
                           received_requests=received_requests, 
                           friends=friends)

# Rotta per inviare una richiesta di amicizia
@app.route('/send_friend_request', methods=['POST'])
def send_friend_request():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    username = request.form.get('username')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verifica se l'utente a cui inviare la richiesta esiste
    cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
    receiver = cursor.fetchone()

    if not receiver:
        flash('Utente non trovato.', 'danger')
        return redirect('/friend_requests')

    receiver_id = receiver['id']

    # Controlla se una richiesta di amicizia pendente esiste già tra gli utenti (in entrambe le direzioni)
    cursor.execute('''
        SELECT * FROM friend_requests 
        WHERE (sender_id = %s AND receiver_id = %s) 
        OR (sender_id = %s AND receiver_id = %s)
    ''', (user_id, receiver_id, receiver_id, user_id))
    
    existing_request = cursor.fetchone()

    if existing_request:
        flash('Una richiesta di amicizia è già in sospeso tra di voi.', 'warning')
    else:
        # Controlla se esiste già un'amicizia tra gli utenti
        cursor.execute('''
            SELECT * FROM friends 
            WHERE (user_id_1 = %s AND user_id_2 = %s) 
            OR (user_id_1 = %s AND user_id_2 = %s)
        ''', (user_id, receiver_id, receiver_id, user_id))

        existing_friendship = cursor.fetchone()

        if existing_friendship:
            flash('Siete già amici!', 'info')
        else:
            # Inserisci la richiesta di amicizia
            cursor.execute('''
                INSERT INTO friend_requests (sender_id, receiver_id, status) 
                VALUES (%s, %s, 'pending')
            ''', (user_id, receiver_id))
            conn.commit()
            flash('Richiesta di amicizia inviata con successo!', 'success')

    cursor.close()
    conn.close()

    return redirect('/friend_requests')

# Rotta per rispondere alle richieste di amicizia
@app.route('/respond_friend_request', methods=['POST'])
def respond_friend_request():
    if 'user_id' not in session:
        return redirect('/login')

    request_id = request.form.get('request_id')
    action = request.form.get('action')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verifica se la richiesta esiste
    cursor.execute('SELECT * FROM friend_requests WHERE id = %s', (request_id,))
    request_info = cursor.fetchone()

    if not request_info or request_info['receiver_id'] != session['user_id']:
        flash('Richiesta non trovata o non autorizzata.', 'danger')
    else:
        if action == 'accept':
            # Aggiungi l'amicizia nella tabella "friends"
            cursor.execute('''
                INSERT INTO friends (user_id_1, user_id_2) 
                VALUES (%s, %s)
            ''', (request_info['sender_id'], request_info['receiver_id']))
            conn.commit()
            flash('Richiesta di amicizia accettata!', 'success')
        elif action == 'reject':
            flash('Richiesta di amicizia rifiutata.', 'info')

        # Elimina la richiesta di amicizia (accettata o rifiutata)
        cursor.execute('DELETE FROM friend_requests WHERE id = %s', (request_id,))
        conn.commit()

    cursor.close()
    conn.close()

    return redirect('/friend_requests')

@app.route('/presenze')
@admin_required  # Questa pagina è accessibile solo agli admin
def presenze():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Query per ottenere tutte le presenze
    query = '''
        SELECT p.id, u.nome, u.cognome, p.ora_entrata, p.ora_uscita, DATE(p.ora_entrata) as data
        FROM presenze p
        JOIN users u ON p.user_id = u.id
        ORDER BY data DESC, p.ora_entrata DESC
    '''
    cursor.execute(query)
    presenze = cursor.fetchall()
    cursor.close()
    conn.close()

    # Verifica i dati recuperati
    print("Dati delle presenze:", presenze)

    # Raggruppa le presenze per giorno
    presenze_per_giorno = {}
    for presenza in presenze:
        data = presenza['data']
        if data not in presenze_per_giorno:
            presenze_per_giorno[data] = []

        # Gestione delle frazioni di secondo
        entrata = presenza['ora_entrata'].strftime('%H:%M:%S') if presenza['ora_entrata'] else 'N/A'
        uscita = presenza['ora_uscita'].strftime('%H:%M:%S') if presenza['ora_uscita'] else 'In corso'

        presenze_per_giorno[data].append({
            'id': presenza['id'],
            'nome': presenza['nome'],
            'cognome': presenza['cognome'],
            'entrata': entrata,
            'uscita': uscita
        })

    # Verifica i dati raggruppati
    print("Presenze per giorno:", presenze_per_giorno)

    return render_template('presenze.html', presenze_per_giorno=presenze_per_giorno)

@app.route('/increment-coffee', methods=['POST'])
def increment_coffee():
    print("Incremento caffè chiamato!")
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Utente non autenticato'}), 401

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Impossibile connettersi al database'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Recupera l'utente
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404

        # Incrementa il contatore del caffè
        new_coffee_count = user['coffee_count'] + 1
        cursor.execute('UPDATE users SET coffee_count = %s WHERE id = %s', (new_coffee_count, user_id))
        conn.commit()

        return jsonify({'new_count': new_coffee_count})

    except Error as e:
        print(f"Errore nel database: {e}")
        return jsonify({'error': 'Errore durante l\'operazione'}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)