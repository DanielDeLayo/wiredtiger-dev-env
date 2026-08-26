// Native MongoDB shell implementation of fixed-count 100% Read Workload (Zipfian & Uniform)

const recordCount = parseInt(TestData.recordCount || "300000");
const operationCount = parseInt(TestData.operationCount || "300000");
const distribution = TestData.distribution || "zipfian";
const numThreads = parseInt(TestData.threads || "8");

const ycsbDB = db.getSiblingDB("ycsb");
const collection = ycsbDB.usertable;

if (TestData.loadData) {
    print("Loading " + recordCount + " documents into ycsb.usertable...");
    collection.drop();
    
    // 1KB payload per document (10 fields x 100 bytes)
    const fieldVal = "x".repeat(100);
    const batchSize = 2000;
    let batch = [];
    
    for (let i = 0; i < recordCount; i++) {
        let doc = { _id: i };
        for (let f = 0; f < 10; f++) {
            doc["field" + f] = fieldVal;
        }
        batch.push(doc);
        if (batch.length >= batchSize) {
            collection.insertMany(batch, { ordered: false });
            batch = [];
        }
    }
    if (batch.length > 0) {
        collection.insertMany(batch, { ordered: false });
    }
    print("Data load complete. Collection count: " + collection.countDocuments({}));
}

if (TestData.runWorkload) {
    print("Executing " + operationCount + " read operations (" + distribution + ") across " + numThreads + " threads...");
    
    const isZipf = (distribution === "zipfian");
    const opsPerThread = Math.floor(operationCount / numThreads);
    const threads = [];
    const host = db.getMongo().host;
    
    const workerFn = function(hostStr, count, totalDocs, zipfMode) {
        const client = new Mongo(hostStr);
        const coll = client.getDB("ycsb").usertable;
        for (let i = 0; i < count; i++) {
            let id;
            if (zipfMode) {
                let r = Math.random();
                let rank = Math.floor(Math.pow(r, 3.5) * totalDocs);
                id = rank % totalDocs;
            } else {
                id = Math.floor(Math.random() * totalDocs);
            }
            coll.findOne({ _id: id });
        }
    };
    
    const start = new Date();
    for (let t = 0; t < numThreads; t++) {
        let th = new Thread(workerFn, host, opsPerThread, recordCount, isZipf);
        threads.push(th);
        th.start();
    }
    
    for (let th of threads) {
        th.join();
    }
    
    const elapsedSec = ((new Date()) - start) / 1000;
    const opsPerSec = elapsedSec > 0 ? (operationCount / elapsedSec).toFixed(2) : "inf";
    print("Completed " + operationCount + " operations in " + elapsedSec + "s (" + opsPerSec + " ops/sec)");
}
