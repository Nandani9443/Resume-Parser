# Resume Parser

A Python-based web application that extracts and analyzes information from resumes, evaluates resume scores, predicts fields, and suggests skills and courses. Built using Streamlit, Pandas, and MySQL.

---

## Features

- Upload and parse resumes in various formats (PDF, DOCX, etc.).
- Calculate a **Resume Score** based on content quality.
- Predict the candidate’s field using machine learning/keyword analysis.
- Store and retrieve user data in a **MySQL database**.
- Display actual skills and recommend additional skills or courses.
- Download user data report as a CSV.

---

## Technologies Used

- **Python 3.13**
- **Streamlit** (Web interface)
- **Pandas** (Data handling)
- **PyMySQL** (Database connectivity)
- **MySQL** (Database storage)
- Optional: **Scikit-learn / NLP libraries** for field prediction (if implemented)

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/Nandani9443/Resume-Parser.git
cd Resume-Parser


### 2.  Install dependencies
```bash
pip install -r requirements.txt

### 3. Create a database named `cv`.
- Create a table `user_data` with the required fields:

  | Column Name           | Type         |
  |----------------------|-------------|
  | ID                    | INT (PK, AI)|
  | Name                  | VARCHAR(500)|
  | email                 | VARCHAR(500)|
  | res_score             | VARCHAR(8)  |
  | Timestamp             | VARCHAR(50) |
  | no_of_pages           | VARCHAR(5)  |
  | Predicted_Field       | VARCHAR(255)|
  | User_level            | VARCHAR(100)|
  | Actual_skills         | TEXT        |
  | Recommended_skills    | TEXT        |
  | Recommended_courses   | TEXT        |

- Store database credentials in a `config.py` file:
```python
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "YourPasswordHere"
DB_NAME = "cv"
Important: Add config.py to .gitignore so your credentials are not pushed to GitHub.


---

### **4. Run the Streamlit app**
```markdown
- Start the app with:
```bash
streamlit run app.py
Open the URL shown in the terminal (usually http://localhost:8501) in your browser.

---

### **5. Usage**
```markdown
1. Login with admin credentials (e.g., Nandani / 12345) to view user data.
2. Upload resumes to analyze them.
3. View:
   - Resume Score
   - Predicted Field
   - Actual Skills
   - Recommended Skills
   - Recommended Courses
4. Download a CSV report of all users’ data.

## Folder Structure

Resume-Parser/
├── app.py # Main Streamlit app
├── config.py # Database credentials (ignored in Git)
├── requirements.txt # Python dependencies
├── README.md # Project documentation
└── other modules/files

yaml
Copy code

---

## Contributing

Contributions are welcome! You can:

- Open an issue to report bugs or request features.
- Fork the repository, make changes, and submit a pull request.
- Ensure that sensitive information like database passwords is **never pushed**.

---

## License

This project is licensed under the **MIT License**.  

© 2025 Nandani Agrawal
