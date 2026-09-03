import subprocess
import time
import sys
import os

if __name__ == "__main__":
    # বর্তমান ফোল্ডারের সঠিক ডিরেক্টরি ট্র্যাক করা
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=========================================")
    echo = "🚀 INTIALIZING MISSION-CRITICAL DISPATCH CORE"
    print(echo)
    print("=========================================")

    # ১. ব্যাকগ্রাউন্ডে ব্যাকএন্ড সার্ভার (FastAPI) চালু করা
    print("⚡ Launching Backend server...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=current_dir
    )

    # ২. ব্যাকএন্ড সচল হতে ৩ সেকেন্ড সেফটি বাফার অপেক্ষা করা
    time.sleep(3)

    # ৩. ফ্রন্টএন্ড ওয়েব অ্যাপ ও লগইন গেটওয়ে (Streamlit) চালু করা
    print("🔒 Launching Cybersecurity Gateway Dashboard...")
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app.py"],
            cwd=current_dir
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Crisis Control Platform...")
    finally:
        # ৪. অ্যাপ বন্ধ করলে ব্যাকগ্রাউন্ড ব্যাকএন্ড প্রসেস কিল করা (Port Free রাখা)
        backend_process.terminate()
        print("🔗 Global session safely terminated.")