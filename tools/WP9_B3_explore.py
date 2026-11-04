import pandas as pd, numpy as np
df = pd.read_csv(r"C:\Users\nouir\PFE\data_extra\D12_veremi_extension\mixalldata_clean.csv", usecols=["type","sendTime","sender","senderPseudo","messageID","class"])
print(df.dtypes); print(df["type"].value_counts())
print(df.sendTime.describe())
s = df.groupby("sender").agg(t0=("sendTime","min"),t1=("sendTime","max"),n=("sendTime","size"),cls=("class","nunique"),c=("class","first"),np_=("senderPseudo","nunique"))
print(s.describe()); print((s.cls>1).sum(), "senders w/ multi class")
s["len"]=s.sender if False else 0
print(s.sort_values("t0").head(10)); print(s.sort_values("t0").tail(10))
# sender id digits
sid = s.index.astype(str)
print(pd.Series([len(x) for x in sid]).value_counts())
print(pd.Series([x[:2] for x in sid]).value_counts().head(20))
# pseudo structure
d = df.drop_duplicates("senderPseudo").head(10); print(d)
# messageID monotone with time?
df2 = df.sort_values("sendTime")
print(df2.messageID.is_monotonic_increasing, df2[["sendTime","messageID","sender","class"]].iloc[::300000])
print(df.duplicated().sum(), df.duplicated(["sender","senderPseudo","sendTime"]).sum(), df.messageID.duplicated().sum())
# class vs time hour
df["h"]=(df.sendTime//3600).astype(int)
print(pd.crosstab(df.h, df["class"]).iloc[:, :8])
