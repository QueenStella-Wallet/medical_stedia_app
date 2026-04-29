import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import or_ # Nécessaire pour la recherche multi-critères

app = Flask(__name__)
app.secret_key = "clinique_expert_2026_key"

# --- CONFIGURATION DE LA BASE DE DONNÉES ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'clinique_privee.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODÈLE DE DONNÉES PATIENT ---
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    age = db.Column(db.Integer)
    poids = db.Column(db.Float)
    taille = db.Column(db.Float)
    imc = db.Column(db.Float)
    statut_poids = db.Column(db.String(50))
    glycemie = db.Column(db.Float)
    temp = db.Column(db.Float)
    tension = db.Column(db.String(15))
    groupe = db.Column(db.String(5))
    electro = db.Column(db.String(5))
    diagnostic = db.Column(db.String(50)) # "Urgence" ou "Normal"
    observation = db.Column(db.Text)      # Liste des symptômes
    date = db.Column(db.String(50))

# --- LOGIQUE MÉDICALE : TRANSFUSION ---
def calculer_compatibilite(groupe):
    regles = {
        'O+':  {'d': 'O+, A+, B+, AB+', 'r': 'O+, O-'},
        'O-':  {'d': 'Tous les groupes', 'r': 'O-'},
        'A+':  {'d': 'A+, AB+', 'r': 'A+, A-, O+, O-'},
        'A-':  {'d': 'A+, A-, AB+, AB-', 'r': 'A-, O-'},
        'B+':  {'d': 'B+, AB+', 'r': 'B+, B-, O+, O-'},
        'B-':  {'d': 'B+, B-, AB+, AB-', 'r': 'B-, O-'},
        'AB+': {'d': 'AB+', 'r': 'Tous les groupes'},
        'AB-': {'d': 'AB+, AB-', 'r': 'A-, B-, AB-, O-'}
    }
    return regles.get(groupe, {'d': 'Inconnu', 'r': 'Inconnu'})

# --- ROUTES DE L'APPLICATION ---

@app.route('/')
def index():
    query = request.args.get('q', '')
    if query:
        search = f"%{query}%"
        patients = Patient.query.filter(
            or_(
                Patient.nom.like(search.upper()),
                Patient.prenom.like(search),
                Patient.groupe.like(search.upper()),
                Patient.electro.like(search.upper())
            )
        ).all()
    else:
        patients = Patient.query.all()

    # --- MODIFICATION : Élargissement des compteurs pour l'histogramme ---
    stats = {
        'maigre': 0, 'surpoids': 0, 'obese': 0, 
        'hypotension': 0, 'hypertension': 0, 
        'hypoglycemie': 0, 'hyperglycemie': 0,
        'hypothermie': 0, 'hyperthermie': 0,
        'ss': 0,
        'total_urg': 0, 'total_norm': 0, 'total_global': 0
    }

    for p in patients:
        sang = calculer_compatibilite(p.groupe)
        p.donne_a = sang['d']
        p.recoit_de = sang['r']

        if p.diagnostic == "Urgence":
            stats['total_urg'] += 1
            obs = p.observation if p.observation else ""
            
            # Détection précise pour l'histogramme
            if "Maigreur" in obs: stats['maigre'] += 1
            if "Surpoids" in obs: stats['surpoids'] += 1
            if "Obésité" in obs: stats['obese'] += 1
            
            if "Hypotension" in obs: stats['hypotension'] += 1
            if "Hypertension" in obs: stats['hypertension'] += 1
            
            if "Hypoglycémie" in obs: stats['hypoglycemie'] += 1
            if "Glycémie Élevée" in obs: stats['hyperglycemie'] += 1
            
            if "Hypothermie" in obs: stats['hypothermie'] += 1
            if "Fièvre" in obs: stats['hyperthermie'] += 1
            
            if "SS" in obs: stats['ss'] += 1
        else:
            stats['total_norm'] += 1

    stats['total_global'] = len(patients)
    return render_template('index.html', patients=patients, stats=stats, query=query, mode="liste")

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if request.method == 'POST':
        nom = request.form['nom'].upper()
        prenom = request.form['prenom']
        age = int(request.form['age'])
        poids = float(request.form['poids'])
        taille = float(request.form['taille'])
        temp = float(request.form['temp'])
        glycemie = float(request.form['glycemie'])
        tension_val = request.form['tension']
        electro = request.form['electro']

        imc = round(poids / (taille * taille), 2)
        symptomes = []
        
        # Logique de détection inchangée (bas et haut)
        statut_poids = "Normal"
        if imc >= 30: 
            symptomes.append("Obésité")
            statut_poids = "Obésité"
        elif imc >= 25: 
            symptomes.append("Surpoids")
            statut_poids = "Surpoids"
        elif imc < 18.5:
            symptomes.append("Maigreur excessive")
            statut_poids = "Sous-poids"
            
        if temp >= 38.5: symptomes.append("Fièvre")
        elif temp <= 35.5: symptomes.append("Hypothermie")
        
        if glycemie > 1.10: symptomes.append("Glycémie Élevée")
        elif glycemie < 0.70: symptomes.append("Hypoglycémie")
        
        try:
            systolique = int(tension_val.split('/')[0])
            if systolique >= 14: symptomes.append("Hypertension")
            elif systolique <= 9: symptomes.append("Hypotension")
        except: pass

        if electro == "SS":
            symptomes.append("Drépanocytose SS")

        diag = "Urgence" if symptomes else "Normal"
        obs = ", ".join(symptomes) if symptomes else "Stable"

        nouveau = Patient(
            nom=nom, prenom=prenom, age=age, poids=poids, taille=taille, imc=imc,
            statut_poids=statut_poids,
            glycemie=glycemie, temp=temp, tension=tension_val,
            groupe=request.form['groupe'], electro=electro,
            diagnostic=diag, observation=obs,
            date=datetime.now().strftime('%d/%m/%Y %H:%M')
        )

        db.session.add(nouveau)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('index.html', mode="formulaire")

# --- AJOUT DE LA FONCTION MODIFIER ---
@app.route('/modifier/<int:id>', methods=['GET', 'POST'])
def modifier(id):
    patient = Patient.query.get_or_404(id)
    
    if request.method == 'POST':
        # Récupération des données du formulaire
        patient.nom = request.form['nom'].upper()
        patient.prenom = request.form['prenom']
        patient.age = int(request.form['age'])
        patient.poids = float(request.form['poids'])
        patient.taille = float(request.form['taille'])
        patient.temp = float(request.form['temp'])
        patient.glycemie = float(request.form['glycemie'])
        patient.tension = request.form['tension']
        patient.groupe = request.form['groupe']
        patient.electro = request.form['electro']

        # Recalcul de la logique médicale (identique à l'ajout)
        patient.imc = round(patient.poids / (patient.taille * patient.taille), 2)
        symptomes = []
        
        patient.statut_poids = "Normal"
        if patient.imc >= 30: 
            symptomes.append("Obésité")
            patient.statut_poids = "Obésité"
        elif patient.imc >= 25: 
            symptomes.append("Surpoids")
            patient.statut_poids = "Surpoids"
        elif patient.imc < 18.5:
            symptomes.append("Maigreur excessive")
            patient.statut_poids = "Sous-poids"
            
        if patient.temp >= 38.5: symptomes.append("Fièvre")
        elif patient.temp <= 35.5: symptomes.append("Hypothermie")
        
        if patient.glycemie > 1.10: symptomes.append("Glycémie Élevée")
        elif patient.glycemie < 0.70: symptomes.append("Hypoglycémie")
        
        try:
            systolique = int(patient.tension.split('/')[0])
            if systolique >= 14: symptomes.append("Hypertension")
            elif systolique <= 9: symptomes.append("Hypotension")
        except: pass

        if patient.electro == "SS":
            symptomes.append("Drépanocytose SS")

        patient.diagnostic = "Urgence" if symptomes else "Normal"
        patient.observation = ", ".join(symptomes) if symptomes else "Stable"
        
        # On met à jour la date pour indiquer la modification
        patient.date = datetime.now().strftime('%d/%m/%Y %H:%M')

        db.session.commit()
        return redirect(url_for('index'))

    # Renvoie le même formulaire mais avec l'objet patient pour pré-remplir les champs
    return render_template('index.html', mode="formulaire", patient=patient)

@app.route('/supprimer/<int:id>')
def supprimer(id):
    patient = Patient.query.get(id)
    if patient:
        db.session.delete(patient)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)