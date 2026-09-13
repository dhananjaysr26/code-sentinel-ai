#!/usr/bin/env python3
import argparse
import subprocess
import statistics
import sys

def main():
    parser = argparse.ArgumentParser(description="Run stability evaluation by running review.py multiple times.")
    parser.add_argument("--repo", required=True, help="Path to local git repo")
    parser.add_argument("--base", required=True, help="Base commit/branch")
    parser.add_argument("--target", required=True, help="Target commit/branch")
    parser.add_argument("--provider", default="bedrock", choices=["openai", "bedrock"], help="LLM Provider")
    parser.add_argument("--runs", type=int, default=5, help="Number of times to run the review")
    
    args = parser.parse_args()
    
    print(f"Running evaluation: {args.runs} runs for {args.repo}...")
    
    metrics = {
        "input_tokens": [],
        "output_tokens": [],
        "total_tokens": [],
        "latency_ms": [],
        "mcp_calls": [],
        "findings": []
    }
    
    for i in range(args.runs):
        print(f"\\n--- Run {i+1}/{args.runs} ---")
        try:
            cmd = [
                "python", "review.py",
                "--repo", args.repo,
                "--base", args.base,
                "--target", args.target,
                "--provider", args.provider
            ]
            # Use text=True to get string output. We don't capture stdout entirely 
            # so the user can see the progress of each run in real time.
            # We'll use stdout=subprocess.PIPE and print line by line.
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            run_output = []
            for line in process.stdout:
                print(line, end="")
                run_output.append(line.strip())
                
            process.wait()
            
            if process.returncode != 0:
                print(f"Run {i+1} failed with exit code {process.returncode}")
                continue
                
            # Parse metrics from this run's output
            for line in run_output:
                if line.startswith("Input tokens:"):
                    metrics["input_tokens"].append(int(line.split(":")[1].strip()))
                elif line.startswith("Output tokens:"):
                    metrics["output_tokens"].append(int(line.split(":")[1].strip()))
                elif line.startswith("Total tokens:"):
                    metrics["total_tokens"].append(int(line.split(":")[1].strip()))
                elif line.startswith("Wall-clock latency:"):
                    metrics["latency_ms"].append(int(line.replace("Wall-clock latency:", "").replace("ms", "").strip()))
                elif line.startswith("MCP calls:"):
                    metrics["mcp_calls"].append(int(line.split(":")[1].strip()))
                elif line.startswith("Findings:"):
                    metrics["findings"].append(int(line.split(":")[1].strip()))
                    
        except Exception as e:
            print(f"Run {i+1} encountered an exception: {e}")
            
    print("\\n========================================")
    print("        STABILITY EVALUATION REPORT     ")
    print("========================================")
    completed = len(metrics['input_tokens'])
    print(f"Runs completed successfully: {completed}/{args.runs}")
    
    if completed == 0:
        print("No successful runs to aggregate.")
        return
        
    print(f"Avg Input Tokens:  {statistics.mean(metrics['input_tokens']):.0f} ± {statistics.stdev(metrics['input_tokens']) if completed > 1 else 0:.0f}")
    print(f"Avg Output Tokens: {statistics.mean(metrics['output_tokens']):.0f}")
    print(f"Avg Total Tokens:  {statistics.mean(metrics['total_tokens']):.0f}")
    print(f"Avg Latency (ms):  {statistics.mean(metrics['latency_ms']):.0f} ± {statistics.stdev(metrics['latency_ms']) if completed > 1 else 0:.0f}")
    print(f"Avg MCP Calls:     {statistics.mean(metrics['mcp_calls']):.1f}")
    print(f"Avg Findings:      {statistics.mean(metrics['findings']):.1f} ± {statistics.stdev(metrics['findings']) if completed > 1 else 0:.1f}")

if __name__ == "__main__":
    main()
