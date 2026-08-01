import requests

payload = [
    {
        "Larus Labs": {
            "email": "60302700@udst.edu.qa",
            "candidates": [
                {
                    "name": "Amina Hassan",
                    "age": 24,
                    "email": "60302700@udst.edu.qa",
                    "cv": "https://example.com/cv/amina-hassan.pdf",
                    "phone": "50827742",
                    "major": "Computer Science",
                    "university": "Qatar University",
                    "linkedin": "https://www.linkedin.com/in/aminahassan",
                    "job_title": "Software Engineer",
                    "checking_url": "https://example.com/confirm/amina-hassan",
                },
                {
                    "name": "Yousef Al Marri",
                    "age": 23,
                    "email": "60302700@udst.edu.qa",
                    "cv": "https://example.com/cv/yousef-almarri.pdf",
                    "phone": "50827742",
                    "major": "Software Engineering",
                    "university": "UDST",
                    "linkedin": "https://www.linkedin.com/in/yousefalmarri",
                    "job_title": "Backend Developer",
                    "checking_url": "https://example.com/confirm/yousef-almarri",
                },
            ],
        }
    },
    {
        "Quantum AI": {
            "email": "60302700@udst.edu.qa",
            "candidates": [
                {
                    "name": "Fatima Al Kuwari",
                    "age": 22,
                    "email": "60302700@udst.edu.qa",
                    "cv": "https://example.com/cv/fatima-alkuwari.pdf",
                    "phone": "50827742",
                    "major": "Artificial Intelligence",
                    "university": "UDST",
                    "linkedin": "https://www.linkedin.com/in/fatimaalkuwari",
                    "job_title": "Machine Learning Engineer",
                    "checking_url": "https://example.com/confirm/fatima-alkuwari",
                },
                {
                    "name": "Omar Rahman",
                    "age": 25,
                    "email": "60302700@udst.edu.qa",
                    "cv": "https://example.com/cv/omar-rahman.pdf",
                    "phone": "50827742",
                    "major": "Information Systems",
                    "university": "Carnegie Mellon University Qatar",
                    "linkedin": "https://www.linkedin.com/in/omarrahman",
                    "job_title": "Full Stack Developer",
                    "checking_url": "https://example.com/confirm/omar-rahman",
                },
            ],
        }
    },
]

resp = requests.post("http://127.0.0.1:8000/dataentry", json=payload, timeout=60)
print("Status:", resp.status_code)
print(resp.text)
