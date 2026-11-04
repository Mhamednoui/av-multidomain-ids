import pandas as pd, numpy as np
df = pd.read_csv(r"C:\Users\nouir\PFE\data_extra\D12_veremi_extension\mixalldata_clean.csv", usecols=["sendTime","sender","senderPseudo","class"])
s = df.groupby("sender").agg(t0=("sendTime","min"),t1=("sendTime","max"),n=("sendTime","size"),c=("class","first"),np_=("senderPseudo","nunique")).reset_index()
for m in (6,12,60):
    print(m, s.sender.mod(m).value_counts().sort_index().head(12).to_dict())
s["m6"]=s.sender%6
print(pd.crosstab(s.m6, s.c))
s=s.sort_values("t0")
print(s.sender.diff().describe())
print(s[["sender","t0","c"]].iloc[1000:1030].T)
# sender vs t0 slope
print(np.corrcoef(s.sender, s.t0)[0,1])
# pseudonym structure
p = df.drop_duplicates("senderPseudo")
p["pre"]=p.senderPseudo//(10**7) 
print(p.senderPseudo.astype(str).str.len().value_counts())
x = s[s.np_>5].head(3); print(x)
# gaps between sender ids in time: unique ids per hour
print(s.sender.max(), len(s))
