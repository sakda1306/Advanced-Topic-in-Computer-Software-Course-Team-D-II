import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

# 1. อ่านไฟล์ CSV
df = pd.read_csv('data/intents.csv')

# 2. แปลงข้อความ (text) เป็น Feature Vector ด้วย TF-IDF
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(df['text'])
y = df['intent']

# 3. เทรนโมเดล Logistic Regression
model = LogisticRegression()
model.fit(X, y)

# 4. บันทึกโมเดลไว้ใช้งานใน API (/local/classify)
joblib.dump(vectorizer, 'tfidf_vectorizer.pkl')
joblib.dump(model, 'intent_model.pkl')

print("เทรนโมเดลเสร็จเรียบร้อย!")