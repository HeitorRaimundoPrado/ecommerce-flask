
import os
import functools

from sqlite3 import IntegrityError
import json
from flask import Flask, render_template, request, url_for, redirect, session, flash, get_flashed_messages, g, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import stripe


BUYER = 1
SELLER = 2

ALLOWED_EXTENSIONS_IMG = {'png', 'jpg', 'jpeg', 'svg'}
UPLOAD_DIRECTORY = 'imgs'

stripe.api_key = os.environ['STRIPE_SECRET_KEY']

def allowed_filename(filename:str):
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS_IMG

def create_new_offer(img_path: str, price: str, title: str, file, app) -> None:
    from .db import get_db

    error = None

    db = get_db()
    user = db.execute(
            'SELECT * FROM user WHERE id = ?', 
            (str(g.user),)
            ).fetchone()

    username = user['username']
    app.logger.debug(f'user[\'username\'] = { username}')

    try:
        db.execute(
                "INSERT INTO offer (username, price, offername, image) VALUES (?, ?, ?, ?)", 
                (user['username'], price, title, img_path,)
                )
        db.commit()

    except Exception as e:
        error = 'Some error occurred, we are sorry!'
        log_error = e.__str__()
        app.logger.error(f"Error inserting values into database: {log_error}")

    else:
        file.save(os.path.join(app.config['UPLOAD_DIRECTORY'], file.filename))

    if error is None:
        pass

    else:
        flash(error)



def login_user(email: str, password: str) -> int:
    from .db import get_db

    error = None

    db = get_db()

    user = db.execute(
            'SELECT * FROM user WHERE email = ?',
            (email,)
            ).fetchone()

    if user is None:
        error = 'Incorrect Username'

    elif not check_password_hash(user['password'], password):
        error = 'Incorrect Password'

    if error is None:
        session.clear()
        session['user_id'] = user['id']
        session['user_type'] = user['userType']
        return 0

    else:
        flash(error)
        return 1

def register_user(username: str, email: str, password: str, userType: int) -> int:
    from .db import get_db
    error = None
    if not username:
        error = 'Username is required'

    elif not email:
        error = "Email is required"

    elif not password:
        error = 'Password is required'

    db = get_db()
    if error is None:
        try:
            db.execute(
                "INSERT INTO user (username, email, password, userType, shopping_list) VALUES (?, ?, ?, ?, ?)",
                (username, email, generate_password_hash(password), userType, '[]')
                )
            db.commit()
        except db.IntegrityError:
            error = f"{username} or {email} is already registered"

        except Exception as e:
            error = e.__str__()


        else:
            return 0

    flash(error)
    return 1

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
            SECRET_KEY='dev', #change later
            DATABASE=os.path.join(app.instance_path, 'ecommerce.sqlite')
            )

    app.config['UPLOAD_DIRECTORY'] = os.path.join(app.instance_path, UPLOAD_DIRECTORY)

    app.secret_key = b'd93284ufdsaf'
    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)

    else:
        app.config.from_mapping(test_config)


    try:
        os.makedirs(app.instance_path)

    except OSError:
        pass

    try:
        os.makedirs(app.config['UPLOAD_DIRECTORY'])
        
    except OSError:
        pass

    @app.before_request
    def load_logged_user():
        from .db import get_db
        user_id = session.get('user_id')
        app.logger.debug(f"user_id = {user_id}")
        

        if user_id is None:
            g.user = None

        else:

            user = get_db().execute(
                    "SELECT * FROM user WHERE id = ?", (user_id,)
                    ).fetchone()

            g.user = user['id']
            g.username = user['username']



        app.logger.debug(f"Loading { g.user } as user")

    @app.before_request
    def load_cart():
        from .db import get_db
        
        cart_id = list()

        db = get_db()
        if g.user is not None:
            cart_id = json.loads(db.execute(
                "SELECT * FROM user WHERE id = ?", (g.user,)
                ).fetchone()['shopping_list'])

        g.cart = list()

        for item_id in cart_id:
            item = db.execute(
                    "SELECT * FROM offer WHERE id = ?", (item_id,)
                    ).fetchone()
            g.cart.append(item)

    @app.route('/img/<name>')
    def img(name:str):
        return send_from_directory(app.config['UPLOAD_DIRECTORY'], name)

    @app.route("/seller", methods=["GET", "POST"])
    def seller():
        if request.method == 'POST':
            if 'bimage' not in request.files:
                flash('Couldn\'t find file part')
                return redirect(url_for(request.url))

            file = request.files['bimage']
            if file.filename == '' or file.filename is None:
                flash('Please select an image to sell your product')
                return redirect(url_for(request.url))

            if not allowed_filename(file.filename):
                flash('Filename is not allowed')
                return redirect(request.url)

            filename = secure_filename(file.filename)
            create_new_offer(filename, request.form['bprice'], request.form['btitle'],file, app)
            return redirect(url_for('home'))
            


        else:
            if g.user is None:
                flash('You must be logged in as a seller to sell in this website')
                return redirect(url_for('login'))


            error = None
            if session['user_type'] != SELLER:
                error = "User must be seller to sell in this website"
            
            if error is None:
                return render_template('seller.html')

            else:
                flash(error)
                return redirect(url_for('home'))

    @app.route("/", defaults={'search': None})
    @app.route("/<search>")
    def home(search: str):
        from .db import get_db
        db = get_db()
        # flash('Testing error messages')

        if search is not None and search != '':
            offers = db.execute(
                    "SELECT * FROM offer \
                    WHERE offername LIKE ?", (f"%{search}%",)
                    ).fetchall()

        else:
            offers = db.execute(
                    "SELECT * FROM offer"
                    ).fetchall()



        return render_template("index.html", offers=offers)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            if login_user(request.form['bemail'], request.form['bpassword']):
                return redirect(url_for("login"))

            return redirect(url_for("home"))

        else:
            return render_template("login.html")


    @app.route("/register", methods=['GET', 'POST'])
    def register():
        if request.method == "POST":
            if register_user(request.form['busername'], request.form['bemail'], request.form['bpassword'], int(request.form['busertype'])) == 0: # No errors
                return redirect(url_for("login"))

            return redirect(request.url) # if there is error stay in same url

        else:
            return render_template("register.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.route("/checkout", methods=['GET', 'POST'])
    def checkout():
        if g.user is None:
            flash("You must be logged in to checkout")
            return redirect(url_for('login'))

        if request.method == 'POST':
            from .db import get_db

            db = get_db()

            stripe_cart = list()

            for cart_item in g.cart:
                # cart_item = db.execute(
                #         "SELECT * FROM offer WHERE id = ?", (str(cart_item_id),)
                #         ).fetchone()

                # app.logger.debug(f'cart_item_id = {cart_item_id}')

                stripe_cart.append({
                    'price_data' : {
                        'product_data': {
                            'name': cart_item['offername']
                            },
                        'unit_amount': int(cart_item['price']*100),
                        'currency': 'usd',
                        },
                    'quantity': 1,
                    })

            try:
                db.execute(
                        "UPDATE user SET shopping_list = json(?) WHERE id = ?", (str([]), g.user)
                        )
                db.commit()

            except Exception as e:
                flash('Some error occurred, we are sorry!')
                app.logger.debug(e.__str__())
                return url_for('home')

            else:
                pass
                
            checkout_session = stripe.checkout.Session.create(
                    line_items=stripe_cart,
                    payment_method_types=['card'],
                    mode='payment',
                    success_url=request.host_url + 'checkout/success',
                    cancel_url=request.host_url + 'checkout/cancel'
                    )

            return redirect(checkout_session.url)


        from .db import get_db

        products_json = get_db().execute(
                "SELECT * FROM user WHERE id = ?", (g.user,)
                ).fetchone()['shopping_list']

        products_id = json.loads(products_json)
        products = list()

        for id in products_id:
            product = get_db().execute(
                    "SELECT * FROM offer WHERE id = ?", (id,)
                    ).fetchone()
            products.append(product)

        return render_template('checkout.html', products=products)

    @app.route('/product/<int:id>', methods=['GET', 'POST'])
    def product(id):

        from .db import get_db

        if request.method == 'POST':
            user = get_db().execute(
                    "SELECT * FROM user WHERE id = ?", (g.user,)
                    ).fetchone()

            current_products = json.loads(user['shopping_list'])
            app.logger.debug(f"\ncurrent_products = {current_products}")

            current_products.append(id)
            app.logger.debug(f"changed currend_products = {current_products}\n")
            db = get_db()
            db.execute("UPDATE user\nSET shopping_list = json(?)\nWHERE id = ?",
                             (str(current_products),g.user,))
            db.commit()

            


        offer = get_db().execute(
                "SELECT * FROM offer WHERE id = ?", (id,)
                ).fetchone()

        return render_template('product.html', product=offer)

    @app.route('/about')
    def about():
        return render_template('about.html')

    @app.route('/search', methods=['POST'])
    def search():
        return redirect(url_for('home', search=request.form['bsearch']))

    @app.route('/checkout/success')
    def checkout_success():
        return render_template('success.html')

    @app.route('/checkout/cancel')
    def checkout_cancel():
        return render_template('cancel.html')

    from . import db

    db.init_app(app)

    return app

