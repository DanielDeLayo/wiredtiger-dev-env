import argparse
import time
import numpy as np
from pymongo import MongoClient
import multiprocessing as mp

def worker_load(worker_id, num_workers, total_docs, batch_size, host, port):
    client = MongoClient(host, port)
    coll = client['ycsb']['usertable']
    payload = "x" * 100
    docs = []
    
    # Each document is 1KB (10 fields x 100 bytes) matching YCSB
    for i in range(worker_id, total_docs, num_workers):
        doc = {"_id": i}
        for f in range(10):
            doc[f"field{f}"] = payload
        docs.append(doc)
        if len(docs) >= batch_size:
            coll.insert_many(docs, ordered=False)
            docs = []
    if docs:
        coll.insert_many(docs, ordered=False)
    client.close()

def worker_workload(ops_count, total_docs, distribution, write_ratio, host, port, queue):
    client = MongoClient(host, port)
    coll = client['ycsb']['usertable']
    
    if distribution == 'zipfian':
        # Generate Zipfian keys with power law
        keys = (np.random.zipf(a=1.5, size=ops_count) - 1) % total_docs
    else:
        keys = np.random.randint(0, total_docs, size=ops_count)
        
    if write_ratio > 0.0:
        is_write = np.random.random(size=ops_count) < write_ratio
    else:
        is_write = np.zeros(ops_count, dtype=bool)
        
    payload = "u" * 100
    start = time.time()
    for k, do_write in zip(keys, is_write):
        doc_id = int(k)
        if do_write:
            coll.update_one({"_id": doc_id}, {"$set": {"field0": payload}})
        else:
            coll.find_one({"_id": doc_id})
    elapsed = time.time() - start
    queue.put(elapsed)
    client.close()

def main():
    parser = argparse.ArgumentParser(description="High-performance MongoDB fixed-count workload generator")
    parser.add_argument('--action', choices=['load', 'run'], required=True)
    parser.add_argument('--records', type=int, default=300000)
    parser.add_argument('--operations', type=int, default=300000)
    parser.add_argument('--distribution', choices=['zipfian', 'uniform'], default='zipfian')
    parser.add_argument('--write-ratio', type=float, default=0.0, help="Ratio of write operations (0.0 to 1.0)")
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=27017)
    args = parser.parse_args()

    client = MongoClient(args.host, args.port)
    coll = client['ycsb']['usertable']

    if args.action == 'load':
        print(f"Loading {args.records} documents into ycsb.usertable...")
        coll.drop()
        
        num_workers = min(args.threads, mp.cpu_count())
        procs = []
        for i in range(num_workers):
            p = mp.Process(target=worker_load, args=(i, num_workers, args.records, 2000, args.host, args.port))
            procs.append(p)
            p.start()
        for p in procs:
            p.join()
            
        print(f"Load complete. Total documents: {coll.count_documents({})}")
        
    elif args.action == 'run':
        write_pct = int(args.write_ratio * 100)
        print(f"Executing {args.operations} fixed-count operations ({args.distribution}, {write_pct}% writes) across {args.threads} workers...")
        ops_per_worker = args.operations // args.threads
        
        queue = mp.Queue()
        procs = []
        start = time.time()
        
        for _ in range(args.threads):
            p = mp.Process(target=worker_workload, args=(ops_per_worker, args.records, args.distribution, args.write_ratio, args.host, args.port, queue))
            procs.append(p)
            p.start()
            
        for p in procs:
            p.join()
            
        total_time = time.time() - start
        ops_sec = args.operations / total_time if total_time > 0 else 0
        print(f"Completed {args.operations} operations in {total_time:.2f}s ({ops_sec:.2f} ops/sec)")

if __name__ == '__main__':
    main()
