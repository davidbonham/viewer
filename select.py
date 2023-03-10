import argparse
import csv
import os
import shutil
import sys


if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description  = 'Copy selected images to a new folder',
    )
    parser.add_argument('--rating', type=int, help='Minimum rating')
    parser.add_argument('--log', action='store_true', help='Display selected files')

    parser.add_argument('source', help='Path to hot folder')
    parser.add_argument('destination', help='Path to selections folder')
    args = parser.parse_args()

    ratings_file = os.path.join(args.source, 'metadata.csv')
    if not os.path.isfile(ratings_file):
        print(f'ratings file {ratings_file} is missng', file=sys.stderr)

    else:
        if  not os.path.isdir(args.destination):
            if args.log: print(f'creating destination folder {args.destination}', file=sys.stderr)
            os.makedirs(args.destination)

        with open(ratings_file, 'r', newline='') as ratings:
            reader = csv.reader(ratings)

            for path, rating, nl  in reader:
                if int(rating) < args.rating: continue
                name = os.path.basename(path)
                target = os.path.join(args.destination, name)
                if args.log:
                    print(f' copying {name} to {target}')
                    shutil.copyfile(path, target)

