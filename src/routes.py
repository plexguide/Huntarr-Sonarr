from flask import Flask, render_template, request, redirect, url_for
import os
import json

# Configure Flask to use templates and static files from the frontend folder
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'))

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Important: Tell Flask your app might be mounted under a subpath like /huntarr
app.config['APPLICATION_ROOT'] = '/huntarr'  # <-- Set your subpath here


def get_ui_preference():
    """Determine which UI to use based on config and user preference"""
    config_file = os.path.join(os.path.dirname(__file__), 'config/ui_settings.json')
    use_new_ui = False

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                settings = json.load(f)
                use_new_ui = settings.get('use_new_ui', False)
        except Exception as e:
            print(f"Error loading UI settings: {e}")

    ui_param = request.args.get('ui', None)
    if ui_param == 'new':
        use_new_ui = True
    elif ui_param == 'classic':
        use_new_ui = False

    return use_new_ui


@app.route('/')
def index():
    """Root route with UI switching capability"""
    if get_ui_preference():
        return redirect(url_for('new_ui'))
    else:
        return render_template('index.html')


@app.route('/user')
def user_page():
    """User settings page with UI switching capability"""
    if get_ui_preference():
        return redirect(url_for('user_new_ui'))
    else:
        return render_template('user.html')


@app.route('/new')
def new_ui():
    """Route for the new UI homepage"""
    return render_template('new/index.html')


@app.route('/user/new')
def user_new_ui():
    """Route for the new UI user page"""
    return render_template('new/user.html')


if __name__ == '__main__':
    app.run(debug=True)