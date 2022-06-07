# Introduction


A data science project in which we explore the connection between various code hierarchies(methods, classes and packages) in a Java program, 
where we define those connections via two ways:

- Function dependencies inferred from the function call graph. 

- Dependencies inferred from code hierarchies that are "changed together" - in the same git commit, or the same pull request.
  
The former part was implemented via the [soot](https://github.com/soot-oss/soot) library, using a small Java wrapper program 
located at the [following repository](https://github.com/huji-proj-needle2021/genCallgraph)

The latter was implemented by extracting commits and pull requests via GitHub's API as well as `pygit2` and matching them to the code hierarchies in which they reside. 
This was done via hand-rolling a partial Java parser for hierarchy declarations.


These dependencies can be modelled via a graph and analyzed in various ways; check out the [write up](writeup.pdf) for more information.
An interactive visualization of these graphs was implemented via the [Dash](https://plotly.com/dash/) library as a web-app.

This project was done as part of the course ["A Needle in a Data Haystack"](https://shnaton.huji.ac.il/index.php/NewSyl/67978/2/2022/) taken at the Hebrew University of Jerusalem.

# Running

You can build and run the included Dockerfile in order to run the visualization tool as follows:

```shell
docker build -t gitanalysis .
docker run -it -v ./GRAPHS:/app/GRAPHS -p 8050:8050 gitanalysis 
```


And then visit [http://localhost:8050](http://localhost:8050)

The app also includes a section for creating a graph using the call-graph method 
(by invoking the included Java graph generator) for a .jar executable program(
includes a Main class)

Generating graphs from commits/PRs can only be done manually by modifying and running [assocRules.ipynb] with various parameters that need be manually tuned(see writeup).

You can download some pre-made graphs from [here](https://drive.google.com/drive/folders/184gUj24y5Oxlf_I7HUooMdVrkMLCT23t) and insert them into `GRAPHS`. (Generated from [jadx](https://github.com/skylot/jadx), a Java/Android decompiler)