import pandas as pd 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix

def load_dataset(dir_path="./dataset/"): 
    train_df = pd.read_csv(dir_path + "train.csv")
    test_df = pd.read_csv(dir_path + "test.csv") 
    valid_df = pd.read_csv(dir_path + "valid.csv") 
    return [train_df, test_df, valid_df]

def inspect_dataset(train_df, test_df, valid_df): 
    print("Train Dataset") 
    print(train_df)
    print(test_df) 
    print(valid_df)

def inspect_model(model, valid): 
    y_pred = model.predict(valid["text"])
    
    print("Confusion matrix:")
    print(confusion_matrix(valid["label"], y_pred))
    
    print(classification_report(
        valid["label"],
        y_pred,
        target_names=["AI-generated", "Human-written"]
    ))

def train(dir_path="./dataset/"):
    # load dataset 
    result = load_dataset() 
    train, test, valid = result[0], result[1], result[2]
    inspect_dataset(train, test, valid) 

        # train the model 
    model = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=50000, ngram_range=(1, 2))),
        ("classifier", LogisticRegression(max_iter=1000, verbose=1))
    ])
    
    # MAGE: label 0 = AI, label 1 = human
    print("Starting training") 
    model.fit(train["text"], train["label"])
    print("Finishing training")

    inspect_model(model, valid)

    return model 

    

    
