import json
import argparse
import sys

def score_signal(signal):
    score = 0
    title = signal['title'].lower()
    summary = signal['summary'].lower()
    category = signal['category'].lower()
    
    # Heuristics for "Transformation Potential"
    keywords = ['agent', 'infrastructure', 'verification', 'governance', 'protocol', 'identity', 'trust']
    
    for word in keywords:
        if word in title or word in summary:
            score += 2
            
    if category in ['agents', 'infrastructure', 'fintech']:
        score += 3
        
    if "autonomous" in summary or "control" in summary:
        score += 2
        
    return score

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Path to input json file')
    args = parser.parse_args()
    
    try:
        if args.input:
            with open(args.input, 'r') as f:
                signals = json.load(f)
        else:
            # Read from stdin if no file
            input_data = sys.stdin.read()
            if not input_data:
                print("No input provided")
                return
            signals = json.loads(input_data)
            
        # Score and Sort
        for sig in signals:
            sig['score'] = score_signal(sig)
            
        # Sort descending by score
        ranked_signals = sorted(signals, key=lambda x: x['score'], reverse=True)
        
        # Return top 3
        print(json.dumps(ranked_signals[:3], indent=2))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
