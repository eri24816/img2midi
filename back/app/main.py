from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import base64
import traceback
from .notation_to_parameter import notation_to_parameters
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add a test API endpoint
@app.get("/test")
async def test():
    return {"message": "This is a message from backend"}

@app.post("/analyze-notation")
async def analyze_notation(request: Request):
    """Process base64 encoded image data"""
    
    try:
        # Print raw request body
        body = await request.body()
        body = json.loads(body.decode('utf-8'))
        image_bytes = base64.b64decode(body['image'])
        parameters = notation_to_parameters(image_bytes)
        result = {}
        result['control_length'] = parameters['intensity'].shape[1]

        for key, value in parameters.items():
            parameters[key] = value.tolist()

        result['parameters'] = parameters
        print(result)
            
        return result
    
    except Exception as e:
        traceback.print_exc()
        raise e

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
