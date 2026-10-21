import pandas as pd, glob, sys
d = r"C:\Users\nouir\PFE\data_extra\D23_cse-cic-ids2018\raw\\"
for f in sorted(glob.glob(d + "*.csv")):
    h = pd.read_csv(f, nrows=2)
    print(f.split("\\")[-1], len(h.columns))
    print(list(h.columns))
    break
h = pd.read_csv(d + "Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv", nrows=3)
print(list(h.columns)); print(h.iloc[:2].T.head(12))
a = pd.read_csv(d + "Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv", nrows=3)
print(a.iloc[:2, :6])
b = pd.read_csv(r"C:\Users\nouir\PFE\data_extra\D10_cicids2017_generated_flows\extracted\TrafficLabelling\Monday-WorkingHours.pcap_ISCX.csv", nrows=3)
print([c for c in b.columns])
