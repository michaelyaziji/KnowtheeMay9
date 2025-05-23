# KnowThee.AI - Leadership Assessment Tool

An AI-powered leadership assessment and development tool that generates personalized leadership profiles from various document inputs.

## Font Installation (Optional)

The application tries to use DejaVuSans font for PDF generation. If you want to use this font instead of the default Helvetica:

1. Create a "fonts" directory in the root of the application (if it doesn't exist)
2. Download DejaVuSans.ttf font and place it in the fonts directory

```
KnowtheeApp/
├── fonts/
│   └── DejaVuSans.ttf
└── ...
```

If the font is not available, the application will fall back to using standard fonts.

## Features
- Upload and process PDF and DOCX files (CVs, 360s, psychometric assessments)
- AI-powered leadership profile generation
- Privacy-first design
- Export profiles to PDF

## Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

3. Run the application:
```bash
streamlit run app.py
```

## Privacy
This application is designed with privacy in mind:
- No long-term storage of PII without explicit permission
- Data is processed locally where possible
- Temporary storage only for the duration of the session

## License
Proprietary - All rights reserved 