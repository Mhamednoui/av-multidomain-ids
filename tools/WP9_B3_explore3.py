import pandas as pd, numpy as np, json
df = pd.read_csv(r"C:\Users\nouir\PFE\data_extra\D12_veremi_extension\mixalldata_clean.csv", usecols=["sendTime","sender","class","posx","posy","posx_n","posy_n","spdx_n","spdy_n","aclx_n","hedx_n","hedy_n","spdx","spdy"])
sp = json.load(open("results/WP5/splits_veremi.json"))
tr = df[df.sender.astype(str).isin(set(sp["train"]))]
print(len(tr))
g = tr.groupby("class")[["posx_n","posy_n","spdx_n","aclx_n","hedx_n"]].agg(["mean","std","min"])
pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
print(g.round(4))
print((tr.posx_n==0).groupby(tr["class"]).mean().round(3).to_dict())
print(tr.groupby("class").apply(lambda d: ((d.posx==0)&(d.posy==0)).mean()).round(3).to_dict())
