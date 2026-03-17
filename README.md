# GarageFlow
[![Ask DeepWiki](https://devin.ai/assets/askdeepwiki.png)](https://deepwiki.com/ddttbb/GarageFlow)

GarageFlow is a modern, offline-first desktop application designed to streamline the management of a car garage or automotive service center. Built with PySide6 and a Fluent Design aesthetic, it provides a clean, intuitive, and feature-rich interface for tracking vehicles, customers, and service history.

## ✨ Features

- **Dashboard**: Get an at-a-glance overview of your operations with key statistics, including the total number of vehicles, customers, and services performed. The dashboard also displays a list of the most recent service activities.

- **Vehicle Management**: Maintain a comprehensive database of all vehicles. You can add, edit, and delete vehicle records, storing details such as:
    - Brand, Model, Year, Plate Number
    - Chassis Number and Color
    - A dedicated image for each vehicle
    - Internal notes

- **Customer Relationship Management (CRM)**: Keep detailed records of your clients, both individuals and corporate entities.
    - Store full name, phone, email, and address.
    - Upload a customer photo for easy identification.
    - Link multiple vehicles to a single customer profile.

- **Service History Tracking**: Log every operation performed on a vehicle. Each service entry can include:
    - Operation name (e.g., "Oil Change")
    - A detailed description of the work done
    - Cost of the service, with a built-in KDV (VAT) calculator.

- **User & Role Management**: A secure, multi-user system with different permission levels:
    - **Admin**: Full access to all features, including user management and system logs.
    - **Edit**: Can create and modify records but cannot manage users or settings.
    - **Read**: View-only access to the data.

- **System Auditing**: A dedicated page for administrators to review a detailed log of all significant actions performed by users, providing accountability and a complete audit trail.

- **Offline-First Data**: All application data is stored locally in a single SQLite database file, ensuring your business can run smoothly without requiring a constant internet connection.

## 🛠️ Tech Stack

- **GUI Framework:** [PySide6](https://www.qt.io/qt-for-python)
- **UI Components:** [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)
- **Database:** SQLite (via Python's built-in `sqlite3` module)

## 🚀 Getting Started

Follow these instructions to get a local copy up and running.

### Prerequisites

- Python 3.8+

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/ddttbb/garageflow.git
    cd garageflow
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```sh
    # Create the environment
    python -m venv venv

    # Activate on Windows
    .\venv\Scripts\activate

    # Activate on macOS/Linux
    source venv/bin/activate
    ```

3.  **Install the required packages:**
    ```sh
    pip install PySide6 qfluentwidgets
    ```

4.  **Run the application:**
    ```sh
    python main.py
    ```

## ⚙️ First-Time Setup

When you run GarageFlow for the first time, it will detect that no administrator account exists. A setup dialog will appear, prompting you to create the main admin account by setting a username and password. This account will have full permissions to manage the system, including creating other user accounts with different roles.

## 🗃️ Database

GarageFlow uses a local SQLite database to store all your data. The database file, `garageflow.db`, along with any uploaded images for vehicles (`/images`) and customers (`/photos`), is automatically created in your user's Documents folder:

`~/Documents/GarageFlow/`