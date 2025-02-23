# vue-fastapi-template

A starting point for a vue frontend + fastapi backend repo. It uses ts, vite, and uvicorn.

## install

```bash
pip install -e back
cd front
npm install
```

## run

### Backend
You can run the backend in two ways:

1. Using command line:
```bash
uvicorn back.app.main:app --reload
```

2. Using VS Code debugger:
- Open the Debug view in VS Code (Ctrl+Shift+D / Cmd+Shift+D)
- Select "FastAPI" from the dropdown
- Press F5 or click the green play button to start debugging

### Frontend
```bash
cd front
npm run dev
```
