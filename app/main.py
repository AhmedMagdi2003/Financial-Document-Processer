from fastapi import FastAPI


def create_app():
    application = FastAPI(title="Impact workspace", version="0.1.0")

    @application.get("/health")
    def health():
        return {"status": "ok", "service": "impact-workspace"}

    return application


app = create_app()
