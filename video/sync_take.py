import subprocess
# ponytail: anchors (raw.mov second, narration second) belong to the 4 Oct 2026 take; re-derive them from a contact sheet for a new take
A=[(0,0),(44.5,11.14),(None,None),(46,11.14),(71,33.86),(98,51.02),(109,53.88),(131.5,56.90),(144.5,59.53),(146.5,62.36),(166.5,65.68),(180,68.09),(189,72.01),(196.5,74.74),(199,78.59),(205,83.88),(212,87.34),(220,91.07),(231.5,94.06),(251,96.55),(267.5,98.88),(269.5,102.34),(294,108.34),(306.5,110.46),(312,112.5),(401,114.46),(434,133.62),(None,None),(813,133.62),(833.5,163.52),(840,172.7)]
segs=[(a[0],b[0],b[1]-a[1]) for a,b in zip(A,A[1:]) if a[0] is not None and b[0] is not None]
C="crop=2560:1440:112:156,scale=1920:1080,setsar=1"
n=len(segs)
g=f"[0:v]{C},split={n}"+"".join(f"[s{i}]" for i in range(n))+";"
for i,(r0,r1,d) in enumerate(segs):
    g+=f"[s{i}]trim={r0}:{r1},setpts=(PTS-STARTPTS)*{d/(r1-r0):.6f},fps=30[v{i}];"
g+="".join(f"[v{i}]" for i in range(n))+f"concat=n={n}:v=1:a=0[o]"
for s in segs: print(s, round(s[2]/(s[1]-s[0]),2))
subprocess.run(["/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg","-y","-v","error","-i","video/raw.mov","-filter_complex",g,"-map","[o]","-an","-c:v","libx264","-preset","veryfast","-crf","14","-pix_fmt","yuv420p","video/raw-sync.mov"],check=True)
