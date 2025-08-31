# app.py (fixed)
import os
import re
import time
import random
import datetime
import base64

import streamlit as st
import pandas as pd
import pymysql
import fitz  # PyMuPDF
import phonenumbers
import spacy
from PIL import Image
from streamlit_tags import st_tags

# Optional YouTube helper
os.environ["PAFY_BACKEND"] = "internal"
try:
    import pafy  # noqa: E402
except Exception:
    pafy = None

# Courses import (keep as-is — ensure Courses.py exists)
from Courses import (
    ds_course,
    web_course,
    android_course,
    ios_course,
    uiux_course,
    resume_videos,
    interview_videos,
)

# Load spaCy once
nlp = spacy.load("en_core_web_sm")

# Heuristics / keywords
BAD_KEYWORDS = [
    "resume", "curriculum", "cv", "linkedin", ".com", "email", "phone", "mobile", "tel",
    "github", "address", "objective", "profile", "summary", "skills", "experience"
]

SKILLS = [
    "Python", "Java", "C++", "JavaScript", "HTML", "CSS",
    "Machine Learning", "Deep Learning", "SQL", "Django",
    "React", "Node.js", "Flask", "AWS", "Data Analysis",
    "Streamlit", "Pandas", "TensorFlow", "Keras", "PyTorch",
    "Android", "Kotlin", "Flutter", "Swift", "iOS", "Figma", "Adobe XD"
]

ds_keyword     = [s.lower() for s in ['tensorflow','keras','pytorch','machine learning','deep learning','flask','streamlit','pandas','scikit-learn','numpy','matplotlib','data science']]
web_keyword    = [s.lower() for s in ['react','django','node js','react js','php','laravel','magento','wordpress','javascript','angular js','c#','flask','html','css']]
android_keyword= [s.lower() for s in ['android','android development','flutter','kotlin','xml','kivy','java']]
ios_keyword    = [s.lower() for s in ['ios','ios development','swift','cocoa','cocoa touch','xcode','objective-c']]
uiux_keyword   = [s.lower() for s in ['ux','adobe xd','figma','zeplin','balsamiq','ui','prototyping','wireframes','storyframes','adobe photoshop','photoshop','illustrator','after effects','premier pro','indesign','user research','user experience']]

# -------------------------
# Name extraction utilities
# -------------------------
def extract_text_from_pdf_raw(pdf_path: str) -> str:
    """Extract full raw text from PDF using PyMuPDF (fitz)."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"
    return full_text.strip()

def extract_text_from_pdf(pdf_path: str) -> tuple[str, int]:
    """Return (text, number_of_pages)."""
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
        pages = len(doc)
    return text.strip(), pages

def extract_first_lines(pdf_path: str, n_lines: int = 8) -> str:
    """Return the first n_lines of the first page as a block of text."""
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        return ""
    text = doc[0].get_text("text")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:n_lines])

def looks_like_name(s: str) -> bool:
    words = [w for w in s.split() if w.strip()]
    if len(words) < 2 or len(words) > 4:
        return False
    if any(ch.isdigit() for ch in s) or "@" in s or any(tok in s.lower() for tok in BAD_KEYWORDS):
        return False
    count_title = sum(1 for w in words if w and (w[0].isupper() or w.isupper()))
    return count_title >= max(1, len(words)-1)

def extract_name_by_font(pdf_path: str) -> str | None:
    """Choose the largest text spans on the first page and return best candidate."""
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        return None
    page = doc[0]
    data = page.get_text("dict")
    spans = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if not txt:
                    continue
                size = span.get("size", 0)
                bbox = span.get("bbox", [0,0,0,0])
                low = txt.lower()
                if any(tok in low for tok in BAD_KEYWORDS) or "@" in txt or len(txt) < 2:
                    continue
                spans.append({"text": txt, "size": size, "y": bbox[1]})
    if not spans:
        return None
    spans.sort(key=lambda s: (-s["size"], s["y"]))
    for cand in spans[:6]:
        if looks_like_name(cand["text"]):
            return cand["text"]
    return spans[0]["text"]

def extract_name_by_ner(text: str) -> str | None:
    """Use regex for explicit 'Name:' patterns and spaCy NER on the provided text chunk."""
    m = re.search(r'(?:Name|Full Name|Candidate)\s*[:\-]\s*([A-Z][A-Za-z\.\s]{1,120})', text, re.I)
    if m:
        candidate = m.group(1).strip()
        if looks_like_name(candidate):
            return candidate
    doc = nlp(text)
    persons = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
    if not persons:
        return None
    for p in persons:
        if looks_like_name(p):
            return p
    return persons[0]

def extract_applicant_name(pdf_path: str) -> str:
    # 1) font/layout heuristics
    try:
        name = extract_name_by_font(pdf_path)
        if name:
            return name
    except Exception:
        pass
    # 2) NER on header
    try:
        header = extract_first_lines(pdf_path, n_lines=10)
        name = extract_name_by_ner(header or "")
        if name:
            return name
    except Exception:
        pass
    # 3) NER on full text
    try:
        full_text = extract_text_from_pdf_raw(pdf_path)
        name = extract_name_by_ner(full_text or "")
        if name:
            return name
    except Exception:
        pass
    return "Name not found"

# -------------------------
# Other extractors
# -------------------------
def extract_email(text: str) -> str | None:
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else None

def extract_phone(text: str) -> str | None:
    try:
        for match in phonenumbers.PhoneNumberMatcher(text, "IN"):
            return phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except Exception:
        pass
    return None

def extract_skills(text: str):
    tl = (text or "").lower()
    found = []
    for skill in SKILLS:
        if skill.lower() in tl:
            found.append(skill)
    return sorted(set(found))

# -------------------------
# Resume parsing / DB
# -------------------------
def parse_resume(pdf_path: str) -> dict:
    text, pages = extract_text_from_pdf(pdf_path)
    name = extract_applicant_name(pdf_path)
    data = {
        "name": name,
        "email": extract_email(text),
        "mobile_number": extract_phone(text),
        "skills": extract_skills(text),
        "no_of_pages": pages,
        "text": text,
    }
    return data

# DB connection - update credentials as needed
# Note: this assumes database 'cv' already exists and your user can connect to it.
# If not, create DB manually or modify this code to create DB before connecting.
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, db=DB_NAME)
cursor = connection.cursor()

def insert_data(name, email, res_score, timestamp, no_of_pages, reco_field, cand_level, skills, recommended_skills, courses):
    DB_table_name = 'user_data'
    insert_sql = (
        f"INSERT INTO {DB_table_name} "
        "(Name, email , res_score, timestamp, no_of_pages, reco_Field, cand_level, skills, recommended_skills, courses) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    rec_values = (name, email, str(res_score), timestamp, str(no_of_pages), reco_field, cand_level, skills, recommended_skills, courses)
    cursor.execute(insert_sql, rec_values)
    connection.commit()

# -------------------------
# UI helpers
# -------------------------
def fetch_yt_video(link: str) -> str:
    if not pafy:
        return "Video"
    try:
        video = pafy.new(link)
        return video.title
    except Exception:
        return "Video"

def get_table_download_link(df: pd.DataFrame, filename: str, text: str) -> str:
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'

def show_pdf(file_path: str) -> None:
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def course_recommender(course_list):
    st.subheader("**Courses & Certificates Recommendations 🎓**")
    c = 0
    rec_course = []
    no_of_recommendations = st.slider('Choose Number of Course Recommendations:', 1, 10, 5)
    random.shuffle(course_list)
    for c_name, c_link in course_list:
        c += 1
        st.markdown(f"({c}) [{c_name}]({c_link})")
        rec_course.append(c_name)
        if c == no_of_recommendations:
            break
    return rec_course

# -------------------------
# Streamlit app
# -------------------------
st.set_page_config(
    page_title="AI Resume Analyzer",
    page_icon='./Logo/logo2.png',
)

def run():
    # header/logo
    if os.path.exists('./Logo/logo2.png'):
        try:
            img = Image.open('./Logo/logo2.png')
            st.image(img)
        except Exception:
            pass

    st.title("AI Resume Analyser")
    st.sidebar.markdown("# Choose User")
    activities = ["User", "Admin"]
    choice = st.sidebar.selectbox("Choose among the given options:", activities)
    link = '[©Developed by Nandani Agrawal](https://www.linkedin.com/in/nandaniagrawal12/)'
    st.sidebar.markdown(link, unsafe_allow_html=True)

    # Create table if not exists
    DB_table_name = 'user_data'
    # NOTE: avoid DEFAULT on TEXT/BLOB columns. Use VARCHAR for short fields.
    table_sql = (
    "CREATE TABLE IF NOT EXISTS " + DB_table_name + """ (
        ID INT NOT NULL AUTO_INCREMENT,
        Name VARCHAR(500) NOT NULL,
        email VARCHAR(500) DEFAULT '',
        resume_score VARCHAR(8) DEFAULT '0',
        Timestamp VARCHAR(50) DEFAULT '',
        Page_no VARCHAR(5) DEFAULT '0',
        Predicted_Field VARCHAR(255) DEFAULT '',
        User_level VARCHAR(100) DEFAULT '',
        Actual_skills TEXT,
        Recommended_skills TEXT,
        Recommended_courses TEXT,
        PRIMARY KEY (ID)
    );
    """
)

    cursor.execute(table_sql)

    if choice == 'User':
        st.markdown("<h5>Upload your resume, and get smart recommendations</h5>", unsafe_allow_html=True)
        pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
        if pdf_file is not None:
            with st.spinner('Uploading your Resume...'):
                time.sleep(1.2)

            upload_dir = "./Uploaded Resume"
            os.makedirs(upload_dir, exist_ok=True)
            save_path = os.path.join(upload_dir, pdf_file.name)
            with open(save_path, "wb") as f:
                f.write(pdf_file.getbuffer())

            show_pdf(save_path)

            resume_data = parse_resume(save_path)
            resume_text = resume_data.get("text", "") or ""
            resume_text_lower = resume_text.lower()

            if resume_data:
                st.header("**Resume Analysis**")
                st.success(f"Hello {resume_data.get('name') or 'there'}")
                st.text(f"Email: {resume_data.get('email') or '-'}")
                st.text(f"Contact: {resume_data.get('mobile_number') or '-'}")
                st.text(f"Resume pages: {resume_data.get('no_of_pages') or '-'}")

                cand_level = ""
                pages = resume_data.get('no_of_pages') or 0
                try:
                    pages = int(pages)
                except Exception:
                    pages = 0

                if pages == 1:
                    cand_level = "Fresher"
                    st.markdown("<h4 style='color:#d73b5c;'>You are at Fresher level!</h4>", unsafe_allow_html=True)
                elif pages == 2:
                    cand_level = "Intermediate"
                    st.markdown("<h4 style='color:#1ed760;'>You are at Intermediate level!</h4>", unsafe_allow_html=True)
                elif pages >= 3:
                    cand_level = "Experienced"
                    st.markdown("<h4 style='color:#fba171;'>You are at Experienced level!</h4>", unsafe_allow_html=True)

                st_tags(label='### Your Current Skills',
                        text='See our skills recommendation below',
                        value=resume_data.get('skills') or [],
                        key='skills_current')

                reco_field = ''
                recommended_skills = []
                rec_course = []

                def any_kw(kws):
                    return any(k in resume_text_lower for k in kws)

                if any_kw(ds_keyword):
                    reco_field = 'Data Science'
                    recommended_skills = ['Data Visualization', 'Predictive Analysis', 'Statistical Modeling', 'Data Mining',
                                          'Clustering & Classification', 'Data Analytics', 'Quantitative Analysis',
                                          'Web Scraping', 'ML Algorithms', 'Keras', 'PyTorch', 'Probability',
                                          'Scikit-learn', 'TensorFlow', 'Flask', 'Streamlit']
                    rec_course = course_recommender(ds_course)
                elif any_kw(web_keyword):
                    reco_field = 'Web Development'
                    recommended_skills = ['React', 'Django', 'Node JS', 'React JS', 'PHP', 'Laravel', 'Magento',
                                          'WordPress', 'JavaScript', 'Angular', 'C#', 'Flask', 'SDK']
                    rec_course = course_recommender(web_course)
                elif any_kw(android_keyword):
                    reco_field = 'Android Development'
                    recommended_skills = ['Android', 'Flutter', 'Kotlin', 'XML', 'Java', 'Kivy', 'GIT', 'SDK', 'SQLite']
                    rec_course = course_recommender(android_course)
                elif any_kw(ios_keyword):
                    reco_field = 'iOS Development'
                    recommended_skills = ['iOS', 'Swift', 'Cocoa', 'Cocoa Touch', 'Xcode', 'Objective-C',
                                          'SQLite', 'Plist', 'StoreKit', 'UI-Kit', 'AV Foundation', 'Auto-Layout']
                    rec_course = course_recommender(ios_course)
                elif any_kw(uiux_keyword):
                    reco_field = 'UI-UX Development'
                    recommended_skills = ['UI', 'User Experience', 'Adobe XD', 'Figma', 'Zeplin', 'Balsamiq',
                                          'Prototyping', 'Wireframes', 'Storyframes', 'Adobe Photoshop', 'Editing',
                                          'Illustrator', 'After Effects', 'Premier Pro', 'InDesign', 'User Research']
                    rec_course = course_recommender(uiux_course)

                # Insert into DB
                ts = time.time()
                cur_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                cur_time = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                timestamp = str(cur_date + '_' + cur_time)

                # Resume writing recommendation (case-insensitive checks)
                st.subheader("**Resume Tips & Ideas💡**")
                resume_score = 0
                if 'objective' in resume_text_lower:
                    resume_score += 20
                    st.markdown('''<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Objective</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5 style='text-align: left; color: #white;'>[-] Please add your career objective, it will give your career intension to the Recruiters.</h5>''', unsafe_allow_html=True)

                if 'experience' in resume_text_lower:
                    resume_score += 20
                    st.markdown('''<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Experience</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5 style='text-align: left; color: #white;'>[-] Please add Experience. It will give the assurance that everything written on your resume is true and fully acknowledged by you</h5>''', unsafe_allow_html=True)

                if ('hobbies' in resume_text_lower) or ('interests' in resume_text_lower):
                    resume_score += 20
                    st.markdown('''<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Hobbies/Interests</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5 style='text-align: left; color: #white;'>[-] Please add Hobbies/Interests. It will show your personality to the Recruiters.</h5>''', unsafe_allow_html=True)

                if 'achievements' in resume_text_lower:
                    resume_score += 20
                    st.markdown('''<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Achievements</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5 style='text-align: left; color: #white;'>[-] Please add Achievements. It will show that you are capable for the required position.</h5>''', unsafe_allow_html=True)

                if 'projects' in resume_text_lower:
                    resume_score += 20
                    st.markdown('''<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Projects</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5 style='text-align: left; color: #white;'>[-] Please add Projects. It will show that you have done work related to the required position.</h5>''', unsafe_allow_html=True)

                # Progress display
                st.subheader("**Resume Score📝**")
                st.markdown(
                    """
                    <style>
                        .stProgress > div > div > div > div {
                            background-color: #d73b5c;
                        }
                    </style>""",
                    unsafe_allow_html=True,
                )
                my_bar = st.progress(0)
                score = 0
                for percent_complete in range(resume_score):
                    score += 1
                    time.sleep(0.01)
                    my_bar.progress(min(percent_complete + 1, 100))
                st.success('** Your Resume Writing Score: ' + str(score) + '**')
                st.warning("** Note: This score is calculated based on the content that you have in your Resume. **")
                st.balloons()

                # Insert row into DB using parsed name & fields
                insert_data(
                    resume_data.get('name'),
                    resume_data.get('email'),
                    str(resume_score),
                    timestamp,
                    str(resume_data.get('no_of_pages')),
                    reco_field,
                    cand_level,
                    str(resume_data.get('skills')),
                    str(recommended_skills),
                    str(rec_course)
                )

                # Bonus videos
                st.header("**Bonus Video for Resume Writing Tips💡**")
                resume_vid = random.choice(resume_videos)
                res_vid_title = fetch_yt_video(resume_vid)
                st.subheader("✅ **" + res_vid_title + "**")
                st.video(resume_vid)

                st.header("**Bonus Video for Interview Tips💡**")
                interview_vid = random.choice(interview_videos)
                int_vid_title = fetch_yt_video(interview_vid)
                st.subheader("✅ **" + int_vid_title + "**")
                st.video(interview_vid)

                connection.commit()
            else:
                st.error('Something went wrong..')

    else:  # Admin side
        st.success('Welcome to Admin Side')
        ad_user = st.text_input("Username")
        ad_password = st.text_input("Password", type='password')
        if st.button('Login'):
            if ad_user == 'Nandani' and ad_password == '12345':
                st.success("Welcome Nandani !")
                cursor.execute('''SELECT * FROM user_data''')
                data = cursor.fetchall()
                st.header("**User's Data**")
                df = pd.DataFrame(data, columns=['ID', 'Name', 'Email', 'Resume Score', 'Timestamp', 'Total Page',
                                                 'Predicted Field', 'User Level', 'Actual Skills', 'Recommended Skills',
                                                 'Recommended Course'])
                st.dataframe(df)
                st.markdown(get_table_download_link(df, 'User_Data.csv', 'Download Report'), unsafe_allow_html=True)
                query = 'select * from user_data;'
                plot_data = pd.read_sql(query, connection)
            else:
                st.error("Invalid username or password. Please try again.")
if __name__ == "__main__":
    run()
