# 🚀 Détection et Correction d'Anomalies dans une Base de Données  

## 📌 Description du Projet  

Ce projet implémente un **système automatisé de détection et correction d'anomalies** dans une base de données relationnelle en utilisant :  
- **PostgreSQL** pour le stockage des données  
- **Apache Airflow** pour l'orchestration des pipelines  
- **Flask** pour l'interface utilisateur  
- **Power BI** pour la visualisation des données  
- **Docker** pour la conteneurisation des services  

Les anomalies détectées (quantités négatives, valeurs nulles, incohérences, etc.) sont affichées sur une interface web et corrigées via des suggestions intelligentes.  


## 📂 Structure du Projet  
📦 anomaly_detection 

├── dags/ # Workflows Apache Airflow

├── logs/ # Logs générés par Airflow

├── plugins/ # Extensions Airflow

├── postgres-data-v2/ # Données PostgreSQL

├── flask/ # Application web Flask

├── docker-compose.yml # Configuration Docker Compose

├── env # Variables d’environnement



├── init_databases.sql # Script d’initialisation de la BDD


## ⚡ Prérequis  
Avant de démarrer le projet, assure-toi d’avoir installé :  
✅ [Docker Desktop](https://www.docker.com/products/docker-desktop)  
✅ [Git](https://git-scm.com/downloads)  
✅ [Power BI Desktop](https://powerbi.microsoft.com/fr-fr/downloads/)  

---

## 🚀 Installation et Déploiement  

### 1️⃣ Cloner le projet  

git clone https://github.com/Marwa-Drief/anomaly_detection.git

cd anomaly_detection

2️⃣ Lancer les services avec Docker

docker-compose up -d

3️⃣ Accéder aux interfaces

PgAdmin : http://localhost:5050

📌 Identifiants : admin@example.com / admin

Apache Airflow : http://localhost:8089

📌 Identifiants : admin / admin

Interface Flask (Anomalies) : http://localhost:5000

Power BI : Ouvrir powerbi_dashboard.pbix et cliquer sur "Actualiser"

📊 Fonctionnalités Principales

✅ Détection automatique des anomalies via Airflow

✅ Interface web pour visualiser et corriger les anomalies

✅ Historisation des anomalies pour suivi et analyse

✅ Intégration avec Power BI pour des tableaux de bord analytiques

✅ Conteneurisation avec Docker pour un déploiement simplifié



📜 Auteurs

👩‍💻 Marwa Drief

👨‍💻 Walid Aadi

👨‍💻 Mohcine Manssouri

📍 Projet réalisé dans le cadre d'un stage chez NTT DATA.

