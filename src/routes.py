from flask import Flask, render_template, request, redirect
import os
import json

# Configure Flask to use templates and static files from the frontend folder
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'))

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

@app.context_processor
def inject_version():
    return { 'version': os.environ.get('HUNTARR_VERSION','unknown') }
    
def get_ui_preference():
    """Determine which UI to use based on config and user preference"""
    # Check if ui_settings.json exists
    config_file = os.path.join(os.path.dirname(__file__), 'config/ui_settings.json')
    
    use_new_ui = False
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                settings = json.load(f)
                use_new_ui = settings.get('use_new_ui', False)
        except Exception as e:
            print(f"Error loading UI settings: {e}")
    
    # Allow URL parameter to override
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
        return redirect('/new')
    else:
        return render_template('index.html')

@app.route('/user')
def user_page():
    """User settings page with UI switching capability"""
    if get_ui_preference():
        return redirect('/user/new')
    else:
        return render_template('user.html')

if __name__ == '__main__':
    app.run(debug=True)
