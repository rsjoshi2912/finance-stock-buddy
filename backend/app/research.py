import argparse
from .db import initialize,SessionLocal
from .engine import utcstamp
from .ingest import now
from .learning import training_rows,save_research_report

def main():
    parser=argparse.ArgumentParser(description='Run an optional walk-forward LightGBM study; never replaces a live model')
    parser.add_argument('--output',required=True)
    parser.add_argument('--asof',default=now())
    parser.add_argument('--allow-sample',action='store_true')
    args=parser.parse_args();initialize()
    with SessionLocal() as session:
        rows=training_rows(session,utcstamp(args.asof),args.allow_sample)
        report=save_research_report(rows,args.output)
        print({k:v for k,v in report.items() if k!='predictions'})

if __name__=='__main__':main()
