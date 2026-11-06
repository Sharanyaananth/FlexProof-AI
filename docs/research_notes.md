	                                                                    Paper 1	Paper 2	Paper 3	FlexProof
What problem does it solve?		
What data does it use (real or simulated)?				
Does it check recovery?				
Does it prove reliability statistically?	


"Measurement of Generative AI Workload Power Profiles for Whole-Facility Data Center Infrastructure Planning"

What problem does it solve?
This paper addresses the challenge of planning data center infrastructure and grid connections in the face of rapidly growing Generative AI energy demands, which has traditionally been difficult because accurate workload power data is kept proprietary by large cloud providers. To solve this, the researchers release an open-source dataset of high-resolution (0.1-second) power measurements for AI training and inference workloads. They also introduce DIPLOEE, a bottom-up simulation model that scales these server-level measurements into realistic, whole-facility energy demand profiles, providing a practical tool for planning grid upgrades, microgrids, and on-site energy generation.

What data does it use (real or simulated)?	
The study uses a combination of real measurements and simulated predictions:
**Real Data:** The researchers recorded the actual electricity used by physical computer chips while running real AI programs. They also used real-world logs from Microsoft Azure and a Shanghai AI lab to see exactly when and how often people submit AI tasks.
**Simulated Data:** They fed those real, small-scale measurements into a computer program to simulate the total energy a massive, hypothetical data center would use over a full year.

Does it check recovery?	
No, the paper does not test or simulate system recovery.

Does it prove reliability statistically?
No, the paper doesn't attempt to mathematically "prove" the reliability of the power grid or the AI models themselves.

"Battery-Assisted Operation of Hyperscale AI Data Centers under Connect-and-Manage Interconnection Practices"
What problem does it solve?		
What data does it use (real or simulated)?				
Does it check recovery?				
Does it prove reliability statistically?	